"""LLM Client - All Gemini API interactions."""
import json
import re
import requests
import pandas as pd
from typing import Optional

from src.config import (
    GEMINI_API_KEY,
    get_gemini_url,
    GEMINI_FLASH,
    GEMINI_PRO,
    EMBEDDING_MODEL,
    TABLE_SCHEMA,
)
from src.prompts import INTENT_PROMPT, NL2SQL_PROMPT, SUMMARY_PROMPT, GENERAL_QA_PROMPT


class LLMClient:
    """Unified client for all Gemini LLM operations."""

    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.api_key = api_key

    def _post(self, url: str, payload: dict) -> dict:
        """Make POST request to Gemini API."""
        resp = requests.post(
            f"{url}?key={self.api_key}",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
        )
        resp.raise_for_status()
        return resp.json()

    def _extract_text(self, response: dict) -> str:
        """Extract text from Gemini response."""
        return response["candidates"][0]["content"]["parts"][0]["text"]

    # -------------------------------------------------------------------------
    # Core LLM Methods
    # -------------------------------------------------------------------------

    def parse_intent(self, user_query: str) -> dict:
        """Parse user query to extract intent, entities, and constraints."""
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

        try:
            result = self._post(get_gemini_url(GEMINI_FLASH), payload)
            text = self._extract_text(result)

            # Extract JSON from response
            start = text.find("{")
            end = text.rfind("}") + 1
            parsed = json.loads(text[start:end])

            # Ensure task is always set
            if not parsed.get("task"):
                parsed["task"] = "query"

            return parsed

        except Exception as e:
            print(f"Intent parse error: {e}")
            default_response["error"] = str(e)
            return default_response

    def generate_sql(self, intent: dict) -> str:
        """Generate SQL query from intent using Gemini Pro."""
        prompt = NL2SQL_PROMPT + f"\n---\nInput JSON: {json.dumps(intent, ensure_ascii=False)}\n"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 5048},
        }

        try:
            result = self._post(get_gemini_url(GEMINI_PRO), payload)
            sql_query = self._extract_text(result).strip()
            return self._normalize_sql_case(sql_query)
        except Exception as e:
            print(f"SQL generation error: {e}")
            return f"-- SQL generation failed: {e}"

    def summarize(self, user_query: str, df: pd.DataFrame) -> str:
        """Generate summary for phone results (up to 4 unique phones)."""
        # Remove duplicates based on Model Name, then limit to 4
        df_unique = df.drop_duplicates(subset=["Model Name"], keep="first")
        df_limited = df_unique.head(4)
        df_json = df_limited.to_json(orient="records")
        
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

        try:
            result = self._post(get_gemini_url(GEMINI_FLASH), payload)
            summary = self._extract_text(result)
            buy_links = self._generate_buy_links(df_limited)
            return summary + buy_links
        except Exception as e:
            return f"Summary Error: {e}"

    def answer_general(self, user_query: str) -> str:
        """Answer general tech questions."""
        prompt = GENERAL_QA_PROMPT.format(user_query=user_query)

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4},
        }

        try:
            result = self._post(get_gemini_url(GEMINI_FLASH), payload)
            return self._extract_text(result)
        except Exception as e:
            return f"Error: {e}"

    def embed(self, text: str) -> Optional[list]:
        """Generate embedding using Gemini embedding model."""
        url = f"https://generativelanguage.googleapis.com/v1beta/{EMBEDDING_MODEL}:embedContent"
        payload = {"content": {"parts": [{"text": text}]}, "model": EMBEDDING_MODEL}

        try:
            resp = requests.post(
                f"{url}?key={self.api_key}",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
            )
            if resp.status_code == 200:
                return resp.json()["embedding"]["values"]
        except Exception as e:
            print(f"Embedding error: {e}")
        return None

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _normalize_sql_case(self, sql_query: str) -> str:
        """Ensure case-insensitive string comparisons in SQL."""
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
