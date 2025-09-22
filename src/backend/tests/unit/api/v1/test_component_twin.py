import uuid
from datetime import datetime, timezone

from fastapi import status
from httpx import AsyncClient


async def _create_flow(client: AsyncClient, headers: dict) -> str:
    payload = {
        "name": f"ctwin-flow-{uuid.uuid4()}",
        "description": "test flow for component twin",
        "data": {},
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert resp.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)
    body = resp.json()
    assert "id" in body
    return body["id"]


async def test_component_twin_crud_basic(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)

    # Create
    create_payload = {
        "flow_id": flow_id,
        "component_id": "Node-XYZ",
        "python_hash": "deadbeef",
        "python_source": "def run(): pass",
        "io_schema": {"inputs": ["text"], "outputs": ["text"]},
        "wit_source": "world echo { export process: func(input: string) -> string; }",
        "rust_source": "pub fn process(s: String) -> String { s }",
        "build_status": "stale",
    }
    resp = await client.post("api/v1/component_twins", json=create_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    created = resp.json()
    twin_id = created["id"]

    assert created["flow_id"] == flow_id
    assert created["component_id"] == "Node-XYZ"
    assert created["build_status"] == "stale"

    # Get
    resp = await client.get(f"api/v1/component_twins/{twin_id}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    fetched = resp.json()
    assert fetched["id"] == twin_id

    # Update
    now = datetime.now(timezone.utc).isoformat()
    update_payload = {
        "build_status": "built",
        "wasm_blob": "local://artifacts/echo_v1.wasm",
        "build_logs_uri": "local://logs/echo_build.log",
        "capability_manifest": {"httpclient": {"allow": ["https://api.example.com"]}},
        "last_verified_at": now,
        "determinism_mode": "strict",
        "parity_metrics": {"text": 0.98, "cosine": 0.996},
    }
    resp = await client.patch(f"api/v1/component_twins/{twin_id}", json=update_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    updated = resp.json()
    assert updated["build_status"] == "built"
    assert updated["wasm_blob"].endswith("echo_v1.wasm")
    assert updated["build_logs_uri"].endswith("echo_build.log")
    assert updated["determinism_mode"] == "strict"
    assert isinstance(updated.get("parity_metrics"), dict)

    # List (by flow)
    resp = await client.get(f"api/v1/component_twins?flow_id={flow_id}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    items = resp.json()
    assert any(it["id"] == twin_id for it in items)

    # List (filter by component_id and build_status)
    resp = await client.get(
        "api/v1/component_twins?component_id=Node-XYZ&build_status=built", headers=logged_in_headers
    )
    assert resp.status_code == status.HTTP_200_OK
    items = resp.json()
    assert any(it["id"] == twin_id for it in items)


async def test_component_twin_roundtrip_complex_fields(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)

    create_payload = {
        "flow_id": flow_id,
        "component_id": "Node-ABC",
        "python_hash": "cafebabe",
        "io_schema": {"inputs": [{"name": "a", "type": "string"}], "outputs": [{"type": "string"}]},
        "capability_manifest": {
            "httpclient": {"allow": ["https://example.com", "https://api.example.com"]},
            "keyvalue": {"namespace": "ns1"},
        },
        "parity_metrics": {"text": 0.91, "cosine": 0.995},
    }
    resp = await client.post("api/v1/component_twins", json=create_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin = resp.json()

    # Fetch and verify JSON fields
    resp = await client.get(f"api/v1/component_twins/{twin['id']}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    fetched = resp.json()
    assert fetched["io_schema"]["inputs"][0]["name"] == "a"
    assert fetched["capability_manifest"]["httpclient"]["allow"][0] == "https://example.com"
    assert 0.9 <= fetched["parity_metrics"]["text"] <= 1.0
