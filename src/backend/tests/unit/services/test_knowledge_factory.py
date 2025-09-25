import types
import sys
import pytest

from langflow.services.knowledge.factory import create_knowledge_client


class DummySettings:
    def __init__(self, backend: str, path: str = "./tmp/lancedb"):
        self.knowledge_backend = backend
        self.knowledge_lancedb_path = path


def test_factory_unknown_backend_raises_value_error():
    s = DummySettings(backend="does-not-exist")
    with pytest.raises(ValueError):
        create_knowledge_client(settings=s)


def test_factory_lancedb_without_dependency_raises(monkeypatch):
    # Ensure adapter imported without lancedb present (adapter tolerates missing import)
    # But instantiating should raise RuntimeError when lancedb is None
    s = DummySettings(backend="lancedb")
    # Ensure any previously loaded lancedb is hidden for the scope of this test
    original = sys.modules.pop("lancedb", None)
    try:
        with pytest.raises(RuntimeError):
            create_knowledge_client(settings=s)
    finally:
        if original is not None:
            sys.modules["lancedb"] = original