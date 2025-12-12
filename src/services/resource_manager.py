"""Resource Manager - Singleton access to all services."""
from functools import lru_cache

from src.services.llm_client import LLMClient
from src.services.db_client import DatabaseClient
from src.services.vector_client import VectorClient
from src.services.query_processor import QueryProcessor


class ResourceManager:
    """Provides shared singleton instances for all services."""

    @property
    @lru_cache(maxsize=1)
    def llm(self) -> LLMClient:
        return LLMClient()

    @property
    @lru_cache(maxsize=1)
    def db(self) -> DatabaseClient:
        return DatabaseClient()

    @property
    @lru_cache(maxsize=1)
    def vector(self) -> VectorClient:
        return VectorClient()

    @property
    @lru_cache(maxsize=1)
    def query_processor(self) -> QueryProcessor:
        return QueryProcessor(
            llm=self.llm,
            db=self.db,
            vector=self.vector,
        )


# Global singleton accessor
resources = ResourceManager()
