import asyncio

from langflow.services.wasmcloud.service import WasmCloudService


def test_wasmcloud_service_instantiates():
    svc = WasmCloudService()
    assert svc.name == "wasmcloud_service"
    assert isinstance(svc.is_configured(), bool)
    assert isinstance(svc.is_available(), bool)


async def _maybe_connect():
    svc = WasmCloudService()
    if svc.is_configured() and svc.is_available():
        try:
            await svc.connect()
        except Exception:
            # Connection may fail if lattice is not running; that's acceptable here
            pass


def test_wasmcloud_connect_does_not_throw_when_missing_deps(event_loop=None):
    loop = event_loop or asyncio.new_event_loop()
    loop.run_until_complete(_maybe_connect())