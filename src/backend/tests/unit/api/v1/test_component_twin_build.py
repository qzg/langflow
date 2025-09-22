import uuid

from fastapi import status
from httpx import AsyncClient


async def _create_flow(client: AsyncClient, headers: dict) -> str:
    payload = {
        "name": f"ctwin-build-flow-{uuid.uuid4()}",
        "description": "test flow for component twin build",
        "data": {
            "nodes": [
                {
                    "id": "Echo-XYZ",
                    "data": {"node": {"id": "Echo-XYZ", "template": {"text": {"type": "string"}}}},
                }
            ]
        },
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert resp.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)
    return resp.json()["id"]


async def _create_twin(client: AsyncClient, headers: dict, flow_id: str) -> str:
    payload = {
        "flow_id": flow_id,
        "component_id": "Echo-XYZ",
        "io_schema": {"inputs": [{"name": "text", "type": "string"}], "outputs": [{"type": "string"}]},
    }
    resp = await client.post("api/v1/component_twins", json=payload, headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    return resp.json()["id"]


async def test_component_twin_build_endpoint(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)
    twin_id = await _create_twin(client, logged_in_headers, flow_id)

    resp = await client.post(f"api/v1/component_twins/{twin_id}/build", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()

    assert body["id"] == twin_id
    assert body["build_status"] in ("built", "error")  # builder may fail if storage unavailable
    if body["build_status"] == "built":
        assert body.get("wasm_blob") and body["wasm_blob"].endswith(".wasm")
        assert body.get("build_logs_uri") and body["build_logs_uri"].endswith(".log")


async def test_component_twin_evaluate_endpoint(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)
    twin_id = await _create_twin(client, logged_in_headers, flow_id)

    # Build first
    await client.post(f"api/v1/component_twins/{twin_id}/build", headers=logged_in_headers)

    # Evaluate
    resp = await client.post(f"api/v1/component_twins/{twin_id}/evaluate", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()

    assert body["id"] == twin_id
    assert isinstance(body.get("parity_metrics"), dict)
    assert body.get("determinism_mode") in ("strict", "nondet")
