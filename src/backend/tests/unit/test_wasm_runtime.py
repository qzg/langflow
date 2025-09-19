import pytest

from langflow.services.wasm.service import WasmService


def test_wasm_service_instantiates():
    svc = WasmService()
    assert svc.name == "wasm_service"


def test_wasm_runtime_available_flag_type():
    svc = WasmService()
    # Should return a boolean regardless of wasmtime installation
    assert isinstance(svc.is_available(), bool)