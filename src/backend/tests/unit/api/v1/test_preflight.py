from fastapi import status
from httpx import AsyncClient


async def test_preflight_endpoint_basic(client: AsyncClient):
    response = await client.get("api/v1/preflight")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert isinstance(data, dict)
    assert "ok" in data
    assert "system" in data
    assert "checks" in data
    assert isinstance(data["checks"], list)
    assert "missing" in data
    assert isinstance(data["missing"], list)
    assert "warnings" in data
    assert isinstance(data["warnings"], list)

    # Each check should have at least a name and installed flag
    for check in data["checks"]:
        assert "name" in check
        assert "installed" in check
