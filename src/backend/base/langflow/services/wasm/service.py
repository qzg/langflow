from __future__ import annotations

from typing import Any

from langflow.services.base import Service
from langflow.services.wasm.runtime import WasmInstance, WasmRuntime


class WasmService(Service):
    """Service that provides access to the local Wasmtime runtime.

    This encapsulates the runtime and provides convenience methods for
    checking availability and interacting with component-model binaries.
    """

    name = "wasm_service"

    def __init__(self) -> None:
        self.runtime = WasmRuntime()

    def is_available(self) -> bool:
        """True if Wasmtime is installed and initialized."""
        return self.runtime.available()

    def instantiate(self, path: str) -> WasmInstance:
        """Instantiate a component from a .wasm file path."""
        return self.runtime.instantiate_component(path)

    def call(self, wasm: WasmInstance, export: str, *args: Any) -> Any:
        """Call an export on an instantiated component."""
        return self.runtime.call_export(wasm, export, *args)