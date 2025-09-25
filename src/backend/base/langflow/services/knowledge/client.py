from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Optional


class OpenSearchCompatClient(ABC):
    """Abstract OpenSearch-compatible client surface used by Langflow Knowledge.

    Minimal surface aimed at what Knowledge uses today. Concrete backends must
    implement these methods. Return values should mimic OpenSearch shapes where
    applicable (e.g., hits.hits for search).
    """

    @abstractmethod
    def put_index(self, index: str, *, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create an index (table) with optional schema metadata.
        Should be idempotent.
        """

    @abstractmethod
    def delete_index(self, index: str) -> Dict[str, Any]:
        """Delete the index (table) if it exists."""

    @abstractmethod
    def upsert_doc(self, index: str, *, doc_id: Optional[str], body: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert a single document into the index.
        body should contain vector + metadata and optional text.
        """

    @abstractmethod
    def bulk(self, *, ndjson: Iterable[str]) -> Dict[str, Any]:
        """Process a subset of OpenSearch _bulk NDJSON commands (index/delete)."""

    @abstractmethod
    def search(self, index: str, *, body: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a search with a subset of OS DSL (knn + bool filters)."""