import re
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

    def _to_python_expr(self, pred: str) -> str:
        # Translate simple predicate language to a Python expression using row dict
        expr = pred
        expr = expr.replace(" AND ", " and ").replace(" OR ", " or ")
        # EXISTS(field) -> (row.get('field') is not None)
        expr = re.sub(r"EXISTS\(([^)]+)\)", r"(row.get('\1') is not None)", expr)
        # field == 'value'
        expr = re.sub(r"([A-Za-z_][A-Za-z0-9_]*)\s*==\s*'([^']*)'", r"(row.get('\1') == '\2')", expr)
        # numeric comparisons
        expr = re.sub(r"([A-Za-z_][A-Za-z0-9_]*)\s*>=\s*([0-9]+(?:\.[0-9]+)?)", r"(row.get('\1', 0) >= \2)", expr)
        expr = re.sub(r"([A-Za-z_][A-Za-z0-9_]*)\s*>\s*([0-9]+(?:\.[0-9]+)?)", r"(row.get('\1', 0) > \2)", expr)
        expr = re.sub(r"([A-Za-z_][A-Za-z0-9_]*)\s*<=\s*([0-9]+(?:\.[0-9]+)?)", r"(row.get('\1', 0) <= \2)", expr)
        expr = re.sub(r"([A-Za-z_][A-Za-z0-9_]*)\s*<\s*([0-9]+(?:\.[0-9]+)?)", r"(row.get('\1', 0) < \2)", expr)
        return expr  # noqa: RET504

    def to_list(self):
        rows = list(self.table._rows)
        if self._predicate:
            pred = self._predicate
            pyexpr = self._to_python_expr(pred)

            def keep(row):
                try:
                    return bool(eval(pyexpr, {"__builtins__": {}}, {"row": row}))  # noqa: S307
                except Exception:
                    # Fallback to keep all rows if predicate can't be evaluated
                    return True

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

    def search(self, _vector):
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

    def connect(self, _path):
        return self._db


@pytest.fixture(autouse=True)
def fake_lancedb(monkeypatch):  # noqa: ARG001
    mod = _FakeLanceModule()
    sys.modules["lancedb"] = mod
    # Also patch adapter module-level reference if already imported
    try:
        from langflow.services.knowledge.opensearch_lance import adapter

        adapter.lancedb = mod  # type: ignore[attr-defined]
    except Exception:  # noqa: S110
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


def test_adapter_delete_index_and_search_empty(tmp_path):
    client = LanceDBOpenSearchClient(path=str(tmp_path))
    client.put_index("kb")
    # upsert then delete index
    client.upsert_doc("kb", doc_id="1", body={"id": "1", "vector": [0.0], "metadata": {"author": "alice"}})
    del_res = client.delete_index("kb")
    assert del_res.get("acknowledged")
    # searching after delete should return zero hits (fresh empty table)
    body = {"size": 5, "knn": {"query_vector": [0.0], "k": 5}, "query": {"bool": {}}}
    out = client.search("kb", body=body)
    assert out["hits"]["total"]["value"] == 0


def test_adapter_search_should_terms_range(tmp_path):
    client = LanceDBOpenSearchClient(path=str(tmp_path))
    client.put_index("kb")
    # two categories, ensure OR works, and range filter limits to likes >= 10
    client.upsert_doc("kb", doc_id="1", body={"id": "1", "vector": [0.0], "metadata": {"category": "news", "likes": 5}})
    client.upsert_doc(
        "kb", doc_id="2", body={"id": "2", "vector": [0.0], "metadata": {"category": "blog", "likes": 15}}
    )
    client.upsert_doc(
        "kb", doc_id="3", body={"id": "3", "vector": [0.0], "metadata": {"category": "other", "likes": 20}}
    )
    body = {
        "size": 10,
        "knn": {"query_vector": [0.0], "k": 10},
        "query": {
            "bool": {
                "should": [{"term": {"category": "news"}}, {"term": {"category": "blog"}}],
                "filter": [{"range": {"likes": {"gte": 10}}}],
            }
        },
    }
    out = client.search("kb", body=body)
    hits = out["hits"]["hits"]
    assert len(hits) == 1
    assert hits[0]["_source"]["category"] == "blog"
