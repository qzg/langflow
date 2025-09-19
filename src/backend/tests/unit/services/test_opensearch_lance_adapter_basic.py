import sys
import types

import pytest

from langflow.services.knowledge.opensearch_lance.adapter import LanceDBOpenSearchClient


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
        # Extremely naive predicate handling: only equality on author and simple range
        rows = list(self.table._rows)
        if self._predicate:
            pred = self._predicate
            def keep(row):
                ok = True
                if "author == 'alice'" in pred:
                    ok = ok and row.get("author") == "alice"
                if "likes >= 10" in pred:
                    ok = ok and (row.get("likes", 0) >= 10)
                return ok
            rows = [r for r in rows if keep(r)]
        if isinstance(self._limit, int):
            rows = rows[: self._limit]
        # add fake _distance
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

    def search(self, vector):
        return _FakeQuery(self)


class _FakeDB:
    def __init__(self):
        self._tables = {}

    def table_names(self):
        return list(self._tables.keys())

    def create_table(self, name, data=None, mode=None):
        self._tables[name] = _FakeTable()

    def drop_table(self, name):
        self._tables.pop(name, None)

    def open_table(self, name):
        return self._tables.setdefault(name, _FakeTable())


class _FakeLanceModule(types.ModuleType):
    def __init__(self):
        super().__init__("lancedb")
        self._db = _FakeDB()

    def connect(self, path):
        return self._db


@pytest.fixture(autouse=True)
def fake_lancedb(monkeypatch):
    mod = _FakeLanceModule()
    sys.modules["lancedb"] = mod
    # Also patch adapter module-level reference if already imported
    try:
        import langflow.services.knowledge.opensearch_lance.adapter as adapter
        adapter.lancedb = mod  # type: ignore
    except Exception:
        pass
    yield
    sys.modules.pop("lancedb", None)


def test_adapter_put_upsert_search_basic(tmp_path):
    client = LanceDBOpenSearchClient(path=str(tmp_path))
    # create index
    res = client.put_index("kb")
    assert res.get("acknowledged")

    # upsert a doc
    doc = {
        "id": "1",
        "vector": [0.1, 0.2],
        "metadata": {"author": "alice", "likes": 12},
        "text": "hello",
    }
    client.upsert_doc("kb", doc_id=doc["id"], body=doc)

    # search knn + bool filter
    body = {
        "size": 1,
        "knn": {"query_vector": [0.1, 0.2], "k": 1},
        "query": {"bool": {"must": [{"term": {"author": "alice"}}], "filter": [{"range": {"likes": {"gte": 10}}}]}},
    }
    out = client.search("kb", body=body)
    hits = out["hits"]["hits"]
    assert len(hits) == 1
    assert hits[0]["_source"]["author"] == "alice"