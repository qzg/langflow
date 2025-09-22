from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class WasmRuntimeError(RuntimeError):
    """Raised when WASM runtime operations fail."""


@dataclass
class WasmInstance:
    store: Any
    instance: Any


class WasmRuntime:
    """Thin wrapper around wasmtime with component model support.

    This class gracefully handles environments without the wasmtime package
    so that Langflow can start even when WASM is not configured yet.
    """

    def __init__(self, enable_component_model: bool = True) -> None:
        self._enable_component_model = enable_component_model
        self._engine = None
        self._wasmtime = None
        self._init_error: Exception | None = None
        try:
            import wasmtime  # type: ignore

            self._wasmtime = wasmtime
            cfg = wasmtime.Config()
            # Support both old and new APIs to enable the component model
            try:
                # Newer API
                cfg.wasm_component_model = True  # type: ignore[attr-defined]
            except Exception:
                try:
                    # Older API
                    cfg.set_wasm_component_model(True)  # type: ignore[attr-defined]
                except Exception:
                    # If neither attribute exists, proceed; component model may still be default
                    pass
            self._engine = wasmtime.Engine(cfg)
        except Exception as exc:  # noqa: BLE001
            # Defer failures until use; allow app to boot without wasmtime
            self._init_error = exc
            self._engine = None

    def available(self) -> bool:
        """Return True if wasmtime engine initialized successfully."""
        return self._engine is not None and self._wasmtime is not None

    def ensure_available(self) -> None:
        if not self.available():
            raise WasmRuntimeError("Wasmtime is not available or failed to initialize") from self._init_error

    def instantiate_component(self, path: str) -> WasmInstance:
        """Load and instantiate a .wasm from file path.

        Prefers component-model instantiation. If that fails, falls back to
        classic module instantiation. Returns a WasmInstance containing the
        store and instance; callers can use call_export to invoke exported
        functions.
        """
        self.ensure_available()
        assert self._wasmtime is not None and self._engine is not None  # for type checkers
        wasmtime = self._wasmtime
        engine = self._engine

        # Try component-model first
        try:
            component = wasmtime.Component.from_file(engine, path)
            linker = wasmtime.Linker(engine)
            store = wasmtime.Store(engine)
            instance = linker.instantiate(store, component)
            return WasmInstance(store=store, instance=instance)
        except Exception:
            # Fallback to classic module
            try:
                module = wasmtime.Module.from_file(engine, path)
                linker = wasmtime.Linker(engine)
                store = wasmtime.Store(engine)
                instance = linker.instantiate(store, module)
                return WasmInstance(store=store, instance=instance)
            except Exception as exc:
                raise WasmRuntimeError(f"Failed to instantiate wasm file '{path}': {exc}") from exc

    def call_export(self, wasm: WasmInstance, export: str, *args: Any) -> Any:
        """Call an exported function by name.

        This attempts both attribute and mapping-style access to accommodate
        differences across wasmtime Python versions.
        """
        try:
            exports = wasm.instance.exports(wasm.store)
        except Exception as exc:
            raise WasmRuntimeError("Failed to fetch exports from instance") from exc

        func = None
        # Attribute-style
        try:
            func = getattr(exports, export)
        except Exception:
            func = None
        # Mapping-style
        if func is None:
            try:
                func = exports[export]
            except Exception:
                func = None

        if func is None:
            msg = f"Export '{export}' not found on component instance"
            raise WasmRuntimeError(msg)

        try:
            return func(*args)
        except Exception as exc:
            raise WasmRuntimeError(f"Error calling export '{export}': {exc}") from exc
