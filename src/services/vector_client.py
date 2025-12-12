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


class VectorClient:
    """Unified client for vector search operations."""

    def __init__(
        self,
        api_key: str = PINECONE_API_KEY,
        index_name: str = PINECONE_INDEX_NAME,
    ):
        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.index = self._init_index()
        self._llm = None  # Lazy load to avoid circular import

    @property
    def llm(self):
        """Lazy load LLMClient to avoid circular import."""
        if self._llm is None:
            from src.services.llm_client import LLMClient
            self._llm = LLMClient()
        return self._llm

    def _init_index(self):
        """Initialize Pinecone index (create if not exists)."""
        existing = [i.name for i in self.pc.list_indexes()]

        if self.index_name not in existing:
            self.pc.create_index(
                name=self.index_name,
                dimension=EMBEDDING_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            while not self.pc.describe_index(self.index_name).status["ready"]:
                time.sleep(1)

        return self.pc.Index(self.index_name)

    # -------------------------------------------------------------------------
    # Search Methods
    # -------------------------------------------------------------------------

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
        if not query:
            return None

        embedding = self.llm.embed(query)
        if not embedding:
            return None

        # Build filter
        filter_dict = {}
        if type_filter:
            filter_dict["type"] = type_filter
        if company_filter and type_filter == "model":
            filter_dict["company"] = company_filter.lower()

        # Query Pinecone
        results = self.index.query(
            vector=embedding,
            top_k=1,
            include_metadata=True,
            filter=filter_dict if filter_dict else None,
        )

        matches = results.get("matches", [])
        if matches and matches[0]["score"] > threshold:
            return matches[0]["metadata"].get("original_name")

        return None

    def query_vectors(
        self,
        text: str,
        type_filter: Optional[str] = None,
        company_filter: Optional[str] = None,
        top_k: int = 1,
    ) -> List[dict]:
        """Query vectors with filters and return raw matches."""
        embedding = self.llm.embed(text)
        if not embedding:
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
        return results.get("matches", [])

    # -------------------------------------------------------------------------
    # Index Management
    # -------------------------------------------------------------------------

    def build_index(self, db_path: str = DB_PATH) -> None:
        """Build vector index from database (companies and models)."""
        conn = sqlite3.connect(db_path)

        # Get companies
        df_companies = pd.read_sql_query(
            f'SELECT DISTINCT "Company Name" FROM {TABLE_NAME}', conn
        )
        companies = df_companies["Company Name"].dropna().unique().tolist()

        # Get models with company
        df_models = pd.read_sql_query(
            f'SELECT DISTINCT "Company Name", "Model Name" FROM {TABLE_NAME}', conn
        )
        df_models = df_models.dropna(subset=["Model Name", "Company Name"])
        conn.close()

        # Upload companies
        print(f"Uploading {len(companies)} companies...")
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
            time.sleep(0.5)

        # Upload models
        print(f"Uploading {len(df_models)} models...")
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
            time.sleep(0.5)

        print("Vector index build complete!")
