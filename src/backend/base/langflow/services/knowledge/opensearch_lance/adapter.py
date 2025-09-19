from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

try:
    import lancedb  # type: ignore
except Exception:  # pragma: no cover - optional dependency at runtime
    lancedb = None  # type: ignore

from .dsl import build_predicate_from_bool, extract_knn
from ..client import OpenSearchCompatClient


class LanceDBOpenSearchClient(OpenSearchCompatClient):
    """OpenSearch-compatible client backed by LanceDB (in-process).

    This is a minimal subset sufficient for the Langflow Knowledge use-cases.
    It stores one LanceDB table per OS index and supports vector search with
    basic boolean filters.
    """

    def __init__(self, *, path: str = "./data/lancedb") -> None:
        if lancedb is None:
            raise RuntimeError("lancedb is not installed. Please install lancedb to use LanceDBOpenSearchClient.")
        self._db = lancedb.connect(path)

    # ----- Index management -----
    def put_index(self, index: str, *, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Create table if missing; assume schema with at least id, vector, metadata
        if index not in self._db.table_names():
            self._db.create_table(index, data=[], mode="create")
        return {"acknowledged": True, "index": index}

    def delete_index(self, index: str) -> Dict[str, Any]:
        if index in self._db.table_names():
            self._db.drop_table(index)
        return {"acknowledged": True, "index": index}

    # ----- Documents -----
    def upsert_doc(self, index: str, *, doc_id: Optional[str], body: Dict[str, Any]) -> Dict[str, Any]:
        table = self._db.open_table(index)
        row = {
            "id": doc_id or body.get("id"),
            "vector": body.get("vector"),
            "text": body.get("text"),
        }
        # Inline metadata fields (flatten), if present
        meta = body.get("metadata") or body.get("_source") or {}
        if isinstance(meta, dict):
            row.update(meta)
        table.add([row])
        return {"result": "created", "_id": row.get("id")}

    def bulk(self, *, ndjson: Iterable[str]) -> Dict[str, Any]:
        # Minimal _bulk: expects lines with {"index": {"_index": name, "_id": id}} THEN doc line
        # or {"delete": {"_index": name, "_id": id}}
        import json

        ops = [line.strip() for line in ndjson if line.strip()]
        items = []
        i = 0
        while i < len(ops):
            meta = json.loads(ops[i])
            if "index" in meta:
                idx = meta["index"]["_index"]
                _id = meta["index"].get("_id")
                doc = json.loads(ops[i + 1])
                self.upsert_doc(idx, doc_id=_id, body=doc)
                items.append({"index": {"_index": idx, "_id": _id, "status": 201}})
                i += 2
            elif "delete" in meta:
                idx = meta["delete"]["_index"]
                _id = meta["delete"].get("_id")
                # Soft-delete: not implemented yet; could add a deleted flag
                items.append({"delete": {"_index": idx, "_id": _id, "status": 200}})
                i += 1
            else:
                i += 1
        return {"errors": False, "items": items}

    # ----- Search -----
    def search(self, index: str, *, body: Dict[str, Any]) -> Dict[str, Any]:
        table = self._db.open_table(index)

        size = int(body.get("size", 10))
        offset = int(body.get("from", 0))

        knn = extract_knn(body)
        if knn is not None:
            field, vector, k = knn
            q = table.search(vector)
        else:
            q = table.search(None)  # type: ignore[arg-type]

        query = body.get("query") or {}
        bool_node = query.get("bool") if isinstance(query, dict) else None
        predicate = build_predicate_from_bool(bool_node or {})
        if predicate:
            q = q.where(predicate)

        q = q.limit(size + offset)
        results = q.to_list()

        # Convert results to OS-like hits
        hits = []
        for row in results[offset: offset + size]:
            # Lance returns dict-like rows
            _id = row.get("id")
            score = float(row.get("_distance", 0.0))  # distance may be provided; map to score inversely later
            source = {k: v for k, v in row.items() if k not in {"id", "vector", "_distance"}}
            # simple distance->score mapping: higher is better
            _score = 1.0 / (1.0 + score) if score else 1.0
            hits.append({"_id": _id, "_score": _score, "_source": source})

        return {"hits": {"total": {"value": len(hits), "relation": "eq"}, "hits": hits}}