"""Vector Client - Pinecone operations for semantic search."""
import time
import sqlite3
import pandas as pd
from typing import Optional, Tuple, List
from pinecone import Pinecone, ServerlessSpec

from src.config import (
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    EMBEDDING_DIM,
    DB_PATH,
    TABLE_NAME,
)
from src.utils.logger import log_function_call, log_timing, get_logger

logger = get_logger(__name__)


class VectorClient:
    """Unified client for vector search operations."""

    def __init__(
        self,
        api_key: str = PINECONE_API_KEY,
        index_name: str = PINECONE_INDEX_NAME,
    ):
        logger.info(f"VectorClient initializing with index: {index_name}")
        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.index = self._init_index()
        self._llm = None  # Lazy load to avoid circular import
        logger.info("VectorClient initialized successfully")

    @property
    def llm(self):
        """Lazy load LLMClient to avoid circular import."""
        if self._llm is None:
            from src.services.llm_client import LLMClient
            self._llm = LLMClient()
        return self._llm

    def _init_index(self):
        """Initialize Pinecone index (create if not exists)."""
        logger.debug(f"Initializing Pinecone index: {self.index_name}")
        
        with log_timing("Pinecone index initialization"):
            existing = [i.name for i in self.pc.list_indexes()]
            logger.debug(f"Existing indexes: {existing}")

            if self.index_name not in existing:
                logger.info(f"Creating new index: {self.index_name}")
                self.pc.create_index(
                    name=self.index_name,
                    dimension=EMBEDDING_DIM,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
                logger.info("Waiting for index to be ready...")
                while not self.pc.describe_index(self.index_name).status["ready"]:
                    time.sleep(1)
                logger.info("Index is ready")
            else:
                logger.info(f"Using existing index: {self.index_name}")

            return self.pc.Index(self.index_name)

    # -------------------------------------------------------------------------
    # Search Methods
    # -------------------------------------------------------------------------

    @log_function_call
    def find_similar(
        self,
        query: str,
        type_filter: Optional[str] = None,
        company_filter: Optional[str] = None,
        threshold: float = 0.4,
    ) -> Optional[str]:
        """Find most similar name in vector store.
        
        Args:
            query: Text to search for
            type_filter: 'company' or 'model'
            company_filter: Filter models by company (only for type_filter='model')
            threshold: Minimum similarity score
            
        Returns:
            Matched name or None if no match above threshold
        """
        logger.debug(f"Finding similar for query: '{query}', type: {type_filter}, "
                    f"company: {company_filter}, threshold: {threshold}")
        
        if not query:
            logger.warning("Empty query provided")
            return None

        with log_timing("Vector similarity search"):
            embedding = self.llm.embed(query)
            if not embedding:
                logger.warning("Failed to generate embedding")
                return None

            # Build filter
            filter_dict = {}
            if type_filter:
                filter_dict["type"] = type_filter
            if company_filter and type_filter == "model":
                filter_dict["company"] = company_filter.lower()

            logger.debug(f"Querying with filter: {filter_dict}")

            # Query Pinecone
            results = self.index.query(
                vector=embedding,
                top_k=1,
                include_metadata=True,
                filter=filter_dict if filter_dict else None,
            )

            matches = results.get("matches", [])
            if matches and matches[0]["score"] > threshold:
                matched_name = matches[0]["metadata"].get("original_name")
                score = matches[0]["score"]
                logger.info(f"Found match: '{matched_name}' with score: {score:.4f}")
                return matched_name
            else:
                if matches:
                    logger.debug(f"No match above threshold. Best score: {matches[0]['score']:.4f}")
                else:
                    logger.debug("No matches found")
                return None

    @log_function_call
    def query_vectors(
        self,
        text: str,
        type_filter: Optional[str] = None,
        company_filter: Optional[str] = None,
        top_k: int = 1,
    ) -> List[dict]:
        """Query vectors with filters and return raw matches."""
        logger.debug(f"Querying vectors for text: '{text[:50]}...', top_k: {top_k}")
        
        with log_timing("Vector query"):
            embedding = self.llm.embed(text)
            if not embedding:
                logger.warning("Failed to generate embedding")
                return []

            filter_dict = {}
            if type_filter:
                filter_dict["type"] = type_filter
            if company_filter and type_filter == "model":
                filter_dict["company"] = company_filter.lower()

            results = self.index.query(
                vector=embedding,
                top_k=top_k,
                include_metadata=True,
                filter=filter_dict if filter_dict else None,
            )
            matches = results.get("matches", [])
            logger.info(f"Vector query returned {len(matches)} matches")
            return matches

    # -------------------------------------------------------------------------
    # Index Management
    # -------------------------------------------------------------------------

    @log_function_call
    def build_index(self, db_path: str = DB_PATH) -> None:
        """Build vector index from database (companies and models)."""
        logger.info(f"Building vector index from database: {db_path}")
        
        with log_timing("Vector index build"):
            conn = sqlite3.connect(db_path)

            # Get companies
            logger.debug("Fetching companies from database")
            df_companies = pd.read_sql_query(
                f'SELECT DISTINCT "Company Name" FROM {TABLE_NAME}', conn
            )
            companies = df_companies["Company Name"].dropna().unique().tolist()
            logger.info(f"Found {len(companies)} companies")

            # Get models with company
            logger.debug("Fetching models from database")
            df_models = pd.read_sql_query(
                f'SELECT DISTINCT "Company Name", "Model Name" FROM {TABLE_NAME}', conn
            )
            df_models = df_models.dropna(subset=["Model Name", "Company Name"])
            logger.info(f"Found {len(df_models)} models")
            conn.close()

            # Upload companies
            logger.info(f"Uploading {len(companies)} companies to vector index...")
            uploaded_companies = 0
            for i, company in enumerate(companies):
                emb = self.llm.embed(company)
                if emb:
                    self.index.upsert(
                        vectors=[
                            {
                                "id": f"comp_{i}",
                                "values": emb,
                                "metadata": {"type": "company", "original_name": company},
                            }
                        ]
                    )
                    uploaded_companies += 1
                time.sleep(0.5)
            logger.info(f"Uploaded {uploaded_companies} companies")

            # Upload models
            logger.info(f"Uploading {len(df_models)} models to vector index...")
            uploaded_models = 0
            for i, row in df_models.iterrows():
                model = row["Model Name"]
                company = row["Company Name"]
                emb = self.llm.embed(model)
                if emb:
                    self.index.upsert(
                        vectors=[
                            {
                                "id": f"mod_{i}",
                                "values": emb,
                                "metadata": {
                                    "type": "model",
                                    "original_name": model,
                                    "company": company.lower(),
                                },
                            }
                        ]
                    )
                    uploaded_models += 1
                time.sleep(0.5)
            logger.info(f"Uploaded {uploaded_models} models")

            logger.info("Vector index build complete!")
