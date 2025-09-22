import uuid

from fastapi import status
from httpx import AsyncClient


async def test_generate_wit_from_schema(client: AsyncClient, logged_in_headers):
    # Create a flow
    flow_payload = {
        "name": f"wit-flow-{uuid.uuid4()}",
        "description": "flow for wit synthesis",
        "data": {
            "nodes": [
                {
                    "id": "Echo-123",
                    "data": {
                        "node": {
                            "id": "Echo-123",
                            "template": {
                                "text": {"type": "string"},
                                "repeat": {"type": "int"},
                            },
                        }
                    },
                }
            ]
        },
    }
    resp = await client.post("api/v1/flows/", json=flow_payload, headers=logged_in_headers)
    assert resp.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)
    flow_id = resp.json()["id"]

    # Generate WIT
    req = {
        "flow_id": flow_id,
        "component_id": "Echo-123",
        "world_name": "echo",
    }
    resp = await client.post("api/v1/component_twins/generate_wit", json=req, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin = resp.json()
    wit = twin.get("wit_source")
    assert wit
    assert "world echo" in wit
    assert "type Input = record" in wit
    assert "text: string" in wit
    assert "repeat: s64" in wit
