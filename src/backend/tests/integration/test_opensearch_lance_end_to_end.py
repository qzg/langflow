import sys
import types
import json

from fastapi.testclient import TestClient

from langflow.services.knowledge.opensearch_lance.server import create_app
import langflow.services.knowledge.opensearch_lance.adapter as adapter_mod


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
        if self._predicate:
            pred = self._predicate
            def keep(row):
                ok = True
                if "author == 'alice'" in pred:
                    ok = ok and row.get("author") == "alice"
                return ok
            rows = [r for r in rows if keep(r)]
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


def test_end_to_end_sidecar_with_real_adapter():
    # Patch lancedb both at sys.modules and adapter module-level symbol
    fake = _FakeLanceModule()
    sys.modules["lancedb"] = fake
    adapter_mod.lancedb = fake  # ensure adapter sees it

    app = create_app()
    client = TestClient(app)

    # Create index
    r = client.put("/kb")
    assert r.status_code == 200

    # Bulk insert two docs
    ndjson = "\n".join([
        json.dumps({"index": {"_index": "kb", "_id": "1"}}),
        json.dumps({"id": "1", "vector": [0.1], "text": "hello", "metadata": {"author": "alice"}}),
        json.dumps({"index": {"_index": "kb", "_id": "2"}}),
        json.dumps({"id": "2", "vector": [0.2], "text": "world", "metadata": {"author": "bob"}}),
        "",
    ])
    r = client.post("/_bulk", data=ndjson, headers={"content-type": "application/x-ndjson"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("errors") is False

    # Search for alice
    body = {"size": 5, "knn": {"query_vector": [0.1], "k": 5}, "query": {"bool": {"must": [{"term": {"author": "alice"}}]}}}
    r = client.post("/kb/_search", json=body)
    assert r.status_code == 200
    res = r.json()
    hits = res.get("hits", {}).get("hits", [])
    assert len(hits) == 1
    assert hits[0]["_source"]["author"] == "alice"