from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from ..factory import create_knowledge_client

try:
    # Optional settings integration
    from langflow.services.deps import get_settings_service  # type: ignore
except Exception:  # pragma: no cover
    get_settings_service = None  # type: ignore


def get_settings() -> Optional[object]:  # pragma: no cover - settings may not exist in isolated runs
    if get_settings_service is None:
        return None
    return get_settings_service().settings  # type: ignore


def create_app() -> FastAPI:
    settings = get_settings()
    client = create_knowledge_client(settings=settings)

    app = FastAPI(title="OpenSearch-Compatible LanceDB", version="0.1.0")

    @app.put("/{index}")
    async def put_index(index: str, request: Request) -> JSONResponse:
        try:
            body: Dict[str, Any] = {}
            if request.headers.get("content-type", "").startswith("application/json"):
                body = await request.json()  # optional schema
        except Exception:
            body = {}
        result = client.put_index(index, schema=body or None)
        return JSONResponse(result)

    @app.delete("/{index}")
    async def delete_index(index: str) -> JSONResponse:
        result = client.delete_index(index)
        return JSONResponse(result)

    @app.post("/{index}/_doc")
    async def post_doc(index: str, request: Request) -> JSONResponse:
        body = await request.json()
        doc_id = body.get("id") if isinstance(body, dict) else None
        result = client.upsert_doc(index, doc_id=doc_id, body=body)
        return JSONResponse(result)

    @app.post("/{index}/_doc/{doc_id}")
    async def post_doc_with_id(index: str, doc_id: str, request: Request) -> JSONResponse:
        body = await request.json()
        result = client.upsert_doc(index, doc_id=doc_id, body=body)
        return JSONResponse(result)

    @app.post("/_bulk")
    async def bulk(request: Request) -> JSONResponse:
        # Accept application/x-ndjson or text/plain
        # Read raw text and split by lines
        raw = await request.body()
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        lines: List[str] = [ln for ln in text.splitlines() if ln.strip()]
        result = client.bulk(ndjson=lines)
        return JSONResponse(result)

    @app.post("/{index}/_search")
    async def search(index: str, request: Request) -> JSONResponse:
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        result = client.search(index, body=body)
        return JSONResponse(result)

    @app.post("/_msearch")
    async def msearch() -> JSONResponse:  # minimal stub for now
        raise HTTPException(status_code=501, detail="_msearch not implemented")

    @app.get("/")
    async def root() -> PlainTextResponse:
        return PlainTextResponse("OpenSearch-Compatible LanceDB server")

    return app


# Allow `uvicorn langflow.services.knowledge.opensearch_lance.server:create_app` to run.
app = create_app()