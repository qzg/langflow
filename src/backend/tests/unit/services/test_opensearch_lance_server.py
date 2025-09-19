from fastapi.testclient import TestClient

from langflow.services.knowledge.opensearch_lance.server import create_app


class _FakeClient:
    def __init__(self):
        self.calls = []

    def put_index(self, index, *, schema=None):
        self.calls.append(("put_index", index, schema))
        return {"acknowledged": True, "index": index}

    def delete_index(self, index):
        self.calls.append(("delete_index", index))
        return {"acknowledged": True, "index": index}

    def upsert_doc(self, index, *, doc_id=None, body=None):
        self.calls.append(("upsert_doc", index, doc_id, body))
        return {"result": "created", "_id": doc_id}

    def bulk(self, *, ndjson):
        self.calls.append(("bulk", list(ndjson)))
        return {"errors": False, "items": []}

    def search(self, index, *, body):
        self.calls.append(("search", index, body))
        return {"hits": {"total": {"value": 1, "relation": "eq"}, "hits": [{"_id": "1", "_score": 1.0, "_source": {"ok": True}}]}}


def test_sidecar_endpoints_monkeypatched(monkeypatch):
    fake = _FakeClient()
    # Monkeypatch factory to return fake client
    # Patch the symbol used in the server module (imported via from ..factory import create_knowledge_client)
    import langflow.services.knowledge.opensearch_lance.server as server_mod
    monkeypatch.setattr(server_mod, "create_knowledge_client", lambda settings=None: fake, raising=False)

    app = create_app()
    client = TestClient(app)

    # PUT index
    r = client.put("/kb")
    assert r.status_code == 200
    # POST doc
    r = client.post("/kb/_doc/1", json={"id": "1", "vector": [0.1]})
    assert r.status_code == 200
    # _bulk
    ndjson = '{"index": {"_index": "kb", "_id": "2"}}\n{"id": "2", "vector": [0.2]}\n'
    r = client.post("/_bulk", data=ndjson, headers={"content-type": "application/x-ndjson"})
    assert r.status_code == 200
    # _search
    r = client.post("/kb/_search", json={"size": 1, "query": {"bool": {}}})
    assert r.status_code == 200

    # Inspect recorded calls
    kinds = [c[0] for c in fake.calls]
    assert "put_index" in kinds
    assert "upsert_doc" in kinds
    assert "bulk" in kinds
    assert "search" in kinds