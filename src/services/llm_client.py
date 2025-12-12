"""LLM Client - All Gemini API interactions."""
import json
import re
import requests
import pandas as pd
from typing import Optional, Tuple, Dict, Any

from src.config import (
    GEMINI_API_KEY,
    get_gemini_url,
    GEMINI_FLASH,
    GEMINI_PRO,
    EMBEDDING_MODEL,
    TABLE_SCHEMA,
)
from src.prompts import INTENT_PROMPT, NL2SQL_PROMPT, SUMMARY_PROMPT, GENERAL_QA_PROMPT
from src.utils.logger import log_function_call, log_timing, get_logger
from src.utils.error_handler import APIErrorHandler

logger = get_logger(__name__)


class LLMClient:
    """Unified client for all Gemini LLM operations."""

    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.api_key = api_key
        logger.info("LLMClient initialized")

    @log_function_call
    def _post(self, url: str, payload: dict) -> Tuple[Optional[dict], Optional[Dict[str, Any]]]:
        """Make POST request to Gemini API with error handling.
        
        Returns:
            Tuple of (result, error_info). error_info is None on success.
        """
        def make_request():
            resp = requests.post(
                f"{url}?key={self.api_key}",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=30,  # 30 second timeout
            )
            resp.raise_for_status()
            return resp.json()
        
        with log_timing(f"POST request to {url.split('/')[-1]}"):
            result, error_info = APIErrorHandler.handle_with_retry(
                make_request,
                max_retries=2,
                retry_delay=2.0,
                retry_on_rate_limit=True
            )
            
            if result:
                logger.debug(f"API request successful")
                return result, None
            else:
                logger.warning(f"API request failed: {error_info.get('type') if error_info else 'Unknown'}")
                return None, error_info

    def _extract_text(self, response: dict) -> str:
        """Extract text from Gemini response."""
        return response["candidates"][0]["content"]["parts"][0]["text"]

    # -------------------------------------------------------------------------
    # Core LLM Methods
    # -------------------------------------------------------------------------

    @log_function_call
    def parse_intent(self, user_query: str) -> dict:
        """Parse user query to extract intent, entities, and constraints."""
        logger.info(f"Parsing intent for query: {user_query[:100]}")
        
        with log_timing("Intent parsing"):
            prompt = INTENT_PROMPT.format(table_schema=TABLE_SCHEMA, user_query=user_query)

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 2048},
            }

            default_response = {
                "entities": {"companies": [], "models": []},
                "task": "query",
                "constraints": [],
                "priority_features": {},
                "Refusal_Reason": "",
            }

            result, error_info = self._post(get_gemini_url(GEMINI_FLASH), payload)
            
            if error_info:
                logger.error(f"Intent parse error: {error_info.get('type')}")
                default_response["error"] = error_info
                default_response["error_message"] = APIErrorHandler.get_user_friendly_message(error_info)
                return default_response
            
            try:
                text = self._extract_text(result)
                
                # Extract JSON from response
                start = text.find("{")
                end = text.rfind("}") + 1
                parsed = json.loads(text[start:end])

                # Ensure task is always set
                if not parsed.get("task"):
                    parsed["task"] = "query"

                logger.info(f"Intent parsed successfully. Task: {parsed.get('task')}, "
                          f"Entities: {len(parsed.get('entities', {}).get('companies', []))} companies, "
                          f"{len(parsed.get('entities', {}).get('models', []))} models")
                return parsed

            except (KeyError, IndexError, json.JSONDecodeError) as e:
                logger.error(f"Error parsing intent response: {e}", exc_info=True)
                default_response["error"] = {"type": "invalid_response", "message": "Invalid response format"}
                default_response["error_message"] = "⚠️ **Response Format Error**\n\nI received an unexpected response format. Please try again."
                return default_response

    @log_function_call
    def generate_sql(self, intent: dict) -> str:
        """Generate SQL query from intent using Gemini Pro."""
        logger.info(f"Generating SQL for intent with task: {intent.get('task')}")
        
        with log_timing("SQL generation"):
            prompt = NL2SQL_PROMPT + f"\n---\nInput JSON: {json.dumps(intent, ensure_ascii=False)}\n"

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 5048},
            }

            result, error_info = self._post(get_gemini_url(GEMINI_PRO), payload)
            
            if error_info:
                logger.error(f"SQL generation error: {error_info.get('type')}")
                return None, error_info
            
            try:
                sql_query = self._extract_text(result).strip()
                normalized_sql = self._normalize_sql_case(sql_query)
                logger.info(f"SQL generated successfully. Length: {len(normalized_sql)} chars")
                logger.debug(f"Generated SQL: {normalized_sql[:200]}...")
                return normalized_sql, None
            except (KeyError, IndexError) as e:
                logger.error(f"Error parsing SQL response: {e}", exc_info=True)
                return None, {
                    "type": "invalid_response",
                    "message": "⚠️ **Response Format Error**\n\nI received an unexpected response format. Please try again."
                }

    @log_function_call
    def summarize(self, user_query: str, df: pd.DataFrame) -> str:
        """Generate summary for phone results (up to 4 unique phones)."""
        logger.info(f"Generating summary for {len(df)} phone(s)")
        
        with log_timing("Summary generation"):
            # Remove duplicates based on Model Name, then limit to 4
            df_unique = df.drop_duplicates(subset=["Model Name"], keep="first")
            df_limited = df_unique.head(4)
            df_json = df_limited.to_json(orient="records")
            
            logger.debug(f"Summarizing {len(df_limited)} unique phones from {len(df)} total results")
            
            plural = "s" if len(df_limited) > 1 else ""

            prompt = SUMMARY_PROMPT.format(
                num_phones=len(df_limited),
                plural=plural,
                user_query=user_query,
                total_results=len(df),
                df_json=df_json,
            )

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2},
            }

            result, error_info = self._post(get_gemini_url(GEMINI_FLASH), payload)
            
            if error_info:
                logger.error(f"Summary generation error: {error_info.get('type')}")
                return None, error_info
            
            try:
                summary = self._extract_text(result)
                buy_links = self._generate_buy_links(df_limited)
                final_summary = summary + buy_links
                logger.info(f"Summary generated successfully. Length: {len(final_summary)} chars")
                return final_summary, None
            except (KeyError, IndexError) as e:
                logger.error(f"Error parsing summary response: {e}", exc_info=True)
                return None, {
                    "type": "invalid_response",
                    "message": "⚠️ **Response Format Error**\n\nI received an unexpected response format. Please try again."
                }

    @log_function_call
    def answer_general(self, user_query: str) -> str:
        """Answer general tech questions."""
        logger.info(f"Answering general question: {user_query[:100]}")
        
        with log_timing("General QA"):
            prompt = GENERAL_QA_PROMPT.format(user_query=user_query)

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.4},
            }

            result, error_info = self._post(get_gemini_url(GEMINI_FLASH), payload)
            
            if error_info:
                logger.error(f"General QA error: {error_info.get('type')}")
                return None, error_info
            
            try:
                answer = self._extract_text(result)
                logger.info(f"General QA answered successfully. Length: {len(answer)} chars")
                return answer, None
            except (KeyError, IndexError) as e:
                logger.error(f"Error parsing general QA response: {e}", exc_info=True)
                return None, {
                    "type": "invalid_response",
                    "message": "⚠️ **Response Format Error**\n\nI received an unexpected response format. Please try again."
                }

    @log_function_call
    def embed(self, text: str) -> Optional[list]:
        """Generate embedding using Gemini embedding model."""
        logger.debug(f"Generating embedding for text: {text[:50]}...")
        
        with log_timing("Embedding generation"):
            url = f"https://generativelanguage.googleapis.com/v1beta/{EMBEDDING_MODEL}:embedContent"
            payload = {"content": {"parts": [{"text": text}]}, "model": EMBEDDING_MODEL}

            try:
                resp = requests.post(
                    f"{url}?key={self.api_key}",
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(payload),
                )
                if resp.status_code == 200:
                    embedding = resp.json()["embedding"]["values"]
                    logger.debug(f"Embedding generated successfully. Dimension: {len(embedding)}")
                    return embedding
                else:
                    logger.warning(f"Embedding API returned status {resp.status_code}")
            except Exception as e:
                logger.error(f"Embedding error: {e}", exc_info=True)
        return None

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _normalize_sql_case(self, sql_query: str) -> str:
        """Ensure case-insensitive string comparisons in SQL."""
        logger.debug("Normalizing SQL case for string comparisons")
        string_columns = ["Company Name", "Model Name", "Processor"]
        query = sql_query

        for col in string_columns:
            # Pattern: "Column Name" = 'value'
            pattern1 = rf'"{re.escape(col)}"\s*=\s*([\'"])([^\'"]+)\1'
            replacement1 = f'LOWER("{col}") = LOWER(\\1\\2\\1)'
            query = re.sub(pattern1, replacement1, query, flags=re.IGNORECASE)

            # Pattern: "Column Name" LIKE '%value%'
            pattern2 = rf'"{re.escape(col)}"\s+LIKE\s+([\'"])([^\'"]+)\1'
            replacement2 = f'LOWER("{col}") LIKE LOWER(\\1\\2\\1)'
            query = re.sub(pattern2, replacement2, query, flags=re.IGNORECASE)

        return query

    def _generate_buy_links(self, df: pd.DataFrame) -> str:
        """Generate buy links section for phones."""
        import urllib.parse

        logger.debug(f"Generating buy links for {len(df)} phone(s)")
        buy_section = "\n\n---\n\n## 🛒 Ready to Buy?\n\n"

        for _, row in df.iterrows():
            company = row.get("Company Name", "")
            model = row.get("Model Name", "")
            price = row.get("Launched Price (INR)", 0)

            if not model:
                continue

            search_query = f"{company} {model}".strip()
            encoded = urllib.parse.quote(search_query)

            amazon = f"https://www.amazon.in/s?k={encoded}"
            flipkart = f"https://www.flipkart.com/search?q={encoded}"

            buy_section += f"### {company} {model}\n"
            buy_section += f"**₹{price:,.0f}** | [🛒 Amazon]({amazon}) | [🛒 Flipkart]({flipkart})\n\n"

        buy_section += "*Prices may vary. Links open search results on respective platforms.*\n"
        return buy_section
