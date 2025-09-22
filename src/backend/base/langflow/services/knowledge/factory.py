from __future__ import annotations

import os

from .client import OpenSearchCompatClient
from .opensearch_lance.adapter import LanceDBOpenSearchClient

try:
    # Prefer using the existing settings service if available
    from langflow.services.deps import get_settings_service  # type: ignore
except Exception:  # pragma: no cover
    get_settings_service = None  # type: ignore


def create_knowledge_client(settings: object | None = None) -> OpenSearchCompatClient:
    """Create a Knowledge backend client based on settings.

    This factory prefers a provided settings object (with attributes
    knowledge_backend and knowledge_lancedb_path). If not provided and
    langflow.services.deps.get_settings_service is available, it will fetch
    settings from there.
    """
    if settings is None:
        if get_settings_service is None:  # pragma: no cover - only in isolated tests
            raise RuntimeError("Settings service is not available; provide a settings object.")
        settings = get_settings_service().settings  # type: ignore

    backend = getattr(settings, "knowledge_backend", "lancedb")

    if backend == "lancedb":
        path = getattr(settings, "knowledge_lancedb_path", "./data/lancedb")
        # Ensure the storage directory exists for LanceDB
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            # If directory creation fails, LanceDB may still handle path creation; proceed but log
            # We intentionally don't raise to keep the service usable in read-only contexts
            print(f"[knowledge] Could not ensure LanceDB path {path}: {exc}")
        return LanceDBOpenSearchClient(path=path)

    if backend == "opensearch":  # future backend
        raise NotImplementedError("OpenSearch backend not yet implemented.")

    raise ValueError(f"Unknown knowledge backend: {backend}")
