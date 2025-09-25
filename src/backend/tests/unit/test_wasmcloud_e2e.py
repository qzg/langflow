import asyncio
import os

import pytest
from langflow.services.deps import get_wasmcloud_service

REASON = "E2E requires local lattice; set WASMCLOUD_E2E=1 to enable"


@pytest.mark.skipif(os.getenv("WASMCLOUD_E2E") != "1", reason=REASON)
def test_wasmcloud_connect_e2e():
    loop = asyncio.new_event_loop()

    async def _run():
        svc = get_wasmcloud_service()
        assert svc.is_configured(), "wasmCloud must be enabled for E2E"
        assert svc.is_available(), "nats-py must be installed (uv sync --extra wasmcloud)"
        await svc.connect()
        await svc.disconnect()

    loop.run_until_complete(_run())
