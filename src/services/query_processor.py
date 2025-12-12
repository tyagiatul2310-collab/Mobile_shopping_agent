"""Query Processor - Orchestrates query flow."""
import re
from typing import Optional, Dict, List, Any, Callable
import pandas as pd

from src.services.llm_client import LLMClient
from src.services.db_client import DatabaseClient
from src.services.vector_client import VectorClient
from src.utils.logger import log_function_call, log_timing, get_logger

logger = get_logger(__name__)


class QueryProcessor:
    """Orchestrates the full query processing pipeline."""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        db: Optional[DatabaseClient] = None,
        vector: Optional[VectorClient] = None,
    ):
        self.llm = llm or LLMClient()
        self.db = db or DatabaseClient()
        self.vector = vector or VectorClient()
        logger.info("QueryProcessor initialized")

    @log_function_call
    def process(
        self,
        user_query: str,
        filters: Dict[str, Any],
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Process a user query through the full pipeline.
        
        Args:
            user_query: The user's natural language query
            filters: Sidebar filter dict (company, price_min, price_max, etc.)
            on_status: Optional callback for status updates
            
        Returns:
            Dict with keys: corrections, task, sql, results, content
        """
        logger.info(f"Processing query: {user_query[:100]} with filters: {filters}")
        
        with log_timing("Query processing pipeline"):
            def status(msg: str):
                if on_status:
                    on_status(msg)

            result = {
                "corrections": [],
                "task": None,
                "sql": None,
                "results": None,
                "content": "",
            }

            # Step 1: Parse intent and extract entities
            status("🔍 Analyzing your question...")
            logger.debug("Step 1: Parsing intent")
            intent = self.llm.parse_intent(user_query)

            if intent.get("error"):
                logger.error(f"Intent parsing failed: {intent.get('error')}")
                result["content"] = "❌ **Oops!** I couldn't process your query right now. Please try again in a moment, or rephrase your question."
                return result

            # Extract entities and apply corrections
            logger.debug("Step 2: Applying name corrections")
            entities = intent.pop("entities", {"companies": [], "models": []})
            corrected_query, corrections, company_map = self._apply_corrections(
                user_query, entities
            )
            result["corrections"] = corrections

            if corrections:
                status(f"✅ Corrected {len(corrections)} name(s)")
                logger.info(f"Applied {len(corrections)} corrections: {corrections}")

            # Merge sidebar filters into constraints
            logger.debug("Step 3: Merging filters")
            self._merge_filters(intent, filters)

            # Normalize for case-insensitive matching
            self._normalize_intent(intent)

            # Snap model names in constraints to exact DB values
            self._snap_model_names(intent)

            task = intent.get("task", "query")
            result["task"] = task
            logger.info(f"Task identified: {task}")

            # Get corrected model names
            corrected_models = self._get_corrected_models(entities, company_map)
            
            if task == "general_qa":
                status("💡 Preparing explanation...")
            elif corrected_models:
                status(f"📱 Found {len(corrected_models)} phone(s) to compare")
            else:
                status("🔎 Searching database...")

            # Step 2: Execute based on task
            logger.debug(f"Step 4: Executing task: {task}")
            if task == "general_qa":
                status("✨ Generating detailed explanation...")
                result["content"] = self.llm.answer_general(corrected_query)

            elif task == "query":
                status("🗄️ Searching our phone database...")

                if len(corrected_models) > 1:
                    # Multiple specific models - query each separately
                    logger.info(f"Processing multi-model query for {len(corrected_models)} models")
                    result = self._process_multi_model(
                        corrected_query, corrected_models, result, status
                    )
                else:
                    # Single model or general query
                    logger.info("Processing single query")
                    result = self._process_single_query(
                        corrected_query, intent, result, status
                    )

            elif task == "refusal":
                logger.info(f"Query refused: {intent.get('Refusal_Reason', 'Unknown reason')}")
                result["content"] = f"🚫 **I can't help with that request.** {intent.get('Refusal_Reason', 'Please ask about mobile phones instead.')}"

            else:
                logger.warning(f"Unknown task type: {task}")
                result["content"] = "🤔 **I'm not sure how to help with that.** Please ask about:\n- Phone comparisons\n- Recommendations\n- Phone specifications\n- General tech questions about phones"

            logger.info(f"Query processing completed. Task: {task}, Results: {len(result.get('results', [])) if result.get('results') is not None else 0}")
            return result

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------

    def _apply_corrections(
        self, query: str, entities: Dict[str, List[str]]
    ) -> tuple:
        """Apply vector-based name corrections."""
        logger.debug(f"Applying corrections for {len(entities.get('companies', []))} companies, "
                    f"{len(entities.get('models', []))} models")
        
        with log_timing("Name corrections"):
            corrections = []
            company_map = {}  # original -> corrected
            corrected_query = query

            # Correct companies
            for company in entities.get("companies", []):
                match = self.vector.find_similar(company, type_filter="company")
                if match:
                    company_map[company.lower()] = match
                    if match.lower() != company.lower():
                        corrections.append(f"Company: '{company}' → '{match}'")
                        corrected_query = re.sub(
                            re.escape(company), match, corrected_query, flags=re.IGNORECASE
                        )

            # Correct models (with company context)
            for model in entities.get("models", []):
                model_company = self._detect_model_company(model, company_map)
                match = self.vector.find_similar(
                    model, type_filter="model", company_filter=model_company
                )
                if match and match.lower() != model.lower():
                    corrections.append(f"Model: '{model}' → '{match}'")
                    corrected_query = re.sub(
                        re.escape(model), match, corrected_query, flags=re.IGNORECASE
                    )

            return corrected_query, corrections, company_map

    def _detect_model_company(
        self, model: str, company_map: Dict[str, str]
    ) -> Optional[str]:
        """Detect which company a model belongs to."""
        model_lower = model.lower()
        for orig, corrected in company_map.items():
            if orig in model_lower or corrected.lower() in model_lower:
                return corrected
        # Fallback to first company if only one
        if len(company_map) == 1:
            return list(company_map.values())[0]
        return None

    def _merge_filters(self, intent: Dict, filters: Dict) -> None:
        """Merge sidebar filters into intent constraints."""
        filter_constraints = []

        if filters.get("company"):
            filter_constraints.append({
                "column": "Company Name",
                "operator": "==",
                "value": filters["company"].lower(),
            })

        for col, key_min, key_max in [
            ("Launched Price (INR)", "price_min", "price_max"),
            ("Back Camera (MP)", "camera_min", "camera_max"),
            ("Battery Capacity (mAh)", "battery_min", "battery_max"),
        ]:
            if filters.get(key_min) is not None:
                filter_constraints.append({
                    "column": col, "operator": ">=", "value": filters[key_min]
                })
            if filters.get(key_max) is not None:
                filter_constraints.append({
                    "column": col, "operator": "<=", "value": filters[key_max]
                })

        if not filter_constraints:
            return

        if "constraints" not in intent:
            intent["constraints"] = []

        for fc in filter_constraints:
            # Replace existing or add new
            col, op = fc["column"], fc["operator"]
            found = False
            for i, c in enumerate(intent["constraints"]):
                if c.get("column") == col and c.get("operator") == op:
                    intent["constraints"][i] = fc
                    found = True
                    break
            if not found:
                intent["constraints"].append(fc)

    def _normalize_intent(self, intent: Dict) -> None:
        """Normalize string values to lowercase."""
        string_columns = ["Company Name", "Model Name", "Processor"]

        for c in intent.get("constraints", []):
            if c.get("column") in string_columns and isinstance(c.get("value"), str):
                c["value"] = c["value"].lower()

        if "models_to_compare" in intent:
            intent["models_to_compare"] = [
                m.lower() if isinstance(m, str) else m
                for m in intent["models_to_compare"]
            ]

    def _snap_model_names(self, intent: Dict) -> None:
        """Snap model names in constraints to exact DB values."""
        for c in intent.get("constraints", []):
            if c.get("column") == "Model Name" and isinstance(c.get("value"), str):
                match = self.vector.find_similar(c["value"], type_filter="model")
                if match:
                    c["value"] = match

    def _get_corrected_models(
        self, entities: Dict, company_map: Dict[str, str]
    ) -> List[str]:
        """Get corrected model names for multi-model queries."""
        corrected = []
        for model in entities.get("models", []):
            model_company = self._detect_model_company(model, company_map)
            match = self.vector.find_similar(
                model, type_filter="model", company_filter=model_company
            )
            corrected.append(match if match else model)
        return corrected

    def _process_multi_model(
        self, query: str, models: List[str], result: Dict, status: Callable
    ) -> Dict:
        """Process query with multiple specific models."""
        logger.info(f"Processing multi-model query for {len(models)} models: {models}")
        
        with log_timing("Multi-model processing"):
            all_dfs = []
            all_sqls = []

            for model_name in models:
                logger.debug(f"Processing model: {model_name}")
                single_intent = {
                    "task": "query",
                    "constraints": [{"column": "Model Name", "operator": "==", "value": model_name}],
                    "priority_features": {},
                }
                self._normalize_intent(single_intent)

                sql_query = self.llm.generate_sql(single_intent)
                all_sqls.append(f"-- {model_name}\n{sql_query}")

                if sql_query.strip().lower().startswith("select"):
                    try:
                        df = self.db.query(sql_query)
                        if not df.empty:
                            all_dfs.append(df)
                            status(f"✅ Found: {model_name}")
                            logger.info(f"Found data for {model_name}: {len(df)} rows")
                        else:
                            logger.warning(f"No data found for {model_name}")
                    except Exception as e:
                        logger.error(f"Error querying {model_name}: {e}", exc_info=True)
                        status(f"⚠️ Couldn't find data for {model_name}")

            result["sql"] = "\n\n".join(all_sqls)

            if all_dfs:
                df = pd.concat(all_dfs, ignore_index=True).drop_duplicates()
                result["results"] = df
                status(f"✅ Found {len(df)} phone(s)")
                logger.info(f"Combined results: {len(df)} phones")

                status("📝 Creating detailed comparison...")
                result["content"] = self.llm.summarize(query, df)
            else:
                logger.warning("No data found for any of the requested models")
                result["content"] = "😔 **Sorry, I couldn't find those phones in our database.**\n\n**Try:**\n- Check the spelling of model names\n- Use the sidebar filters to browse available phones\n- Ask for recommendations instead (e.g., 'Best phone under ₹50,000')"

            return result

    def _process_single_query(
        self, query: str, intent: Dict, result: Dict, status: Callable
    ) -> Dict:
        """Process single model or general query."""
        logger.debug("Processing single query")
        
        with log_timing("Single query processing"):
            sql_query = self.llm.generate_sql(intent)
            result["sql"] = sql_query

            if not sql_query.strip().lower().startswith("select"):
                logger.warning("Generated SQL is not a SELECT query")
                result["content"] = "❌ **Sorry, I couldn't generate a proper search query.** Please try rephrasing your question or use the sidebar filters to browse phones."
                return result

            try:
                df = self.db.query(sql_query)
                result["results"] = df
                
                if df.empty:
                    logger.info("Query returned no results")
                    result["content"] = "😔 **No phones found matching your criteria.**\n\n**Suggestions:**\n- Try adjusting your filters in the sidebar\n- Ask for recommendations (e.g., 'Best phone under ₹50,000')\n- Check if the model name is spelled correctly"
                    return result
                
                status(f"✅ Found {len(df)} phone(s)")
                logger.info(f"Query returned {len(df)} results")

                status("📝 Creating detailed comparison...")
                result["content"] = self.llm.summarize(query, df)

            except Exception as e:
                logger.error(f"Error processing single query: {e}", exc_info=True)
                result["content"] = f"❌ **Oops!** Something went wrong while searching. Please try again or rephrase your query."

            return result

