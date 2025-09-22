import json
import sys
import types

import langflow.services.knowledge.opensearch_lance.adapter as adapter_mod
import pytest

# Components under test
from lfx.components.knowledge_bases import KnowledgeIngestionComponent, KnowledgeRetrievalComponent
from lfx.schema.dataframe import DataFrame


class _FakeQuery:
    def __init__(self, table):
        self.table = table
        self._predicate = None
        self._limit = None

    def where(self, predicate: str):
        self._predicate = predicate
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def to_list(self):
        rows = list(self.table._rows)
        # Ignore predicate complexity for this smoke test; return all rows up to limit
        if isinstance(self._limit, int):
            rows = rows[: self._limit]
        out = []
        for r in rows:
            rr = dict(r)
            rr.setdefault("_distance", 0.0)
            out.append(rr)
        return out


class _FakeTable:
    def __init__(self):
        self._rows = []

    def add(self, rows):
        self._rows.extend(rows)

    def search(self, vector):  # noqa: ARG002
        return _FakeQuery(self)


class _FakeDB:
    def __init__(self):
        self._tables = {}

    def table_names(self):
        return list(self._tables.keys())

    def create_table(self, name, data=None, mode=None):  # noqa: ARG002
        self._tables[name] = _FakeTable()

    def drop_table(self, name):
        self._tables.pop(name, None)

    def open_table(self, name):
        return self._tables.setdefault(name, _FakeTable())


class _FakeLanceModule(types.ModuleType):
    def __init__(self):
        super().__init__("lancedb")
        self._db = _FakeDB()

    def connect(self, path):  # noqa: ARG002
        return self._db


class FakeEmbeddings:
    def embed_documents(self, texts):
        # Return a simple 2D vector for each document
        return [[0.1, 0.2] for _ in texts]

    def embed_query(self, text):  # noqa: ARG002
        return [0.1, 0.2]


@pytest.mark.asyncio
async def test_knowledge_ingest_and_retrieve_with_lancedb(tmp_path, monkeypatch):
    # 1) Patch lancedb module and adapter symbol
    fake_lance = _FakeLanceModule()
    sys.modules["lancedb"] = fake_lance
    adapter_mod.lancedb = fake_lance  # ensure adapter sees fake module

    # 2) Settings and paths
    kb_root = tmp_path / "kb_root"
    kb_root.mkdir(parents=True, exist_ok=True)
    lancedb_path = tmp_path / "ldb"
    lancedb_path.mkdir(parents=True, exist_ok=True)

    class _Settings:
        knowledge_backend = "lancedb"
        knowledge_lancedb_path = str(lancedb_path)
        knowledge_bases_dir = str(kb_root)

    class _SettingsService:
        settings = _Settings()

    # 3) Patch settings service in both components
    import lfx.components.knowledge_bases.ingestion as ing_mod
    import lfx.components.knowledge_bases.retrieval as ret_mod

    monkeypatch.setattr(ing_mod, "get_settings_service", lambda: _SettingsService())
    monkeypatch.setattr(ret_mod, "get_settings_service", lambda: _SettingsService())

    # Also patch their module-level KB root constants (in case they were computed at import time)
    monkeypatch.setattr(ing_mod, "KNOWLEDGE_BASES_ROOT_PATH", kb_root, raising=False)
    monkeypatch.setattr(ret_mod, "KNOWLEDGE_BASES_ROOT_PATH", kb_root, raising=False)

    # 4) Patch DB/session and user lookup used by components
    class _User:
        def __init__(self):
            self.id = 1
            self.username = "tester"

    async def _get_user_by_id(_db, _user_id):
        return _User()

    class _SessionCM:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def _session_scope():
        return _SessionCM()

    # Note: get_user_by_id is imported directly in modules
    monkeypatch.setattr(ing_mod, "get_user_by_id", _get_user_by_id, raising=False)
    monkeypatch.setattr(ret_mod, "get_user_by_id", _get_user_by_id, raising=False)
    monkeypatch.setattr(ing_mod, "session_scope", _session_scope, raising=False)
    monkeypatch.setattr(ret_mod, "session_scope", _session_scope, raising=False)

    # 5) Patch embeddings builders to avoid external providers
    monkeypatch.setattr(
        ing_mod.KnowledgeIngestionComponent,
        "_build_embeddings",
        lambda *_args, **_kwargs: FakeEmbeddings(),
        raising=False,
    )
    monkeypatch.setattr(
        ret_mod.KnowledgeRetrievalComponent,
        "_build_embeddings",
        lambda *_args, **_kwargs: FakeEmbeddings(),
        raising=False,
    )

    # 6) Prepare a KB folder and metadata
    kb_name = "kb1"
    kb_dir = kb_root / _User().username / kb_name
    kb_dir.mkdir(parents=True, exist_ok=True)
    (kb_dir / "embedding_metadata.json").write_text(
        json.dumps(
            {
                "embedding_provider": "HuggingFace",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "api_key": None,
                "api_key_used": False,
                "chunk_size": 1000,
                "created_at": "2024-01-01T00:00:00Z",
            }
        )
    )

    # 7) Ingest two simple rows using the component
    ingest = KnowledgeIngestionComponent(
        knowledge_base=kb_name,
        input_df=DataFrame({"text": ["hello world", "lancedb rocks"], "category": ["a", "b"]}),
        column_config=[
            {"column_name": "text", "vectorize": True, "identifier": False},
            {"column_name": "category", "vectorize": False, "identifier": True},
        ],
        chunk_size=1000,
        api_key=None,
        allow_duplicates=False,
        _user_id=_User().id,
    )

    _ = await ingest.build_kb_info()

    # 8) Retrieve via component
    retrieve = KnowledgeRetrievalComponent(
        knowledge_base=kb_name,
        api_key=None,
        search_query="hello",
        top_k=2,
        include_metadata=True,
        include_embeddings=False,
        _user_id=_User().id,
    )

    df = await retrieve.retrieve_data()

    # 9) Assert we got results with content
    assert getattr(df, "data", None), "Expected DataFrame-like result with data"
    rows = df.data  # DataFrame stores a list of Data objects
    assert len(rows) >= 1
    assert any(getattr(r, "content", "") for r in rows)
