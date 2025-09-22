from __future__ import annotations

from typing import Any

from lfx.services.settings.factory import SettingsServiceFactory

from langflow.services.base import Service
from langflow.services.deps import get_service
from langflow.services.schema import ServiceType


class WasmCloudService(Service):
    """Service to integrate with a wasmCloud lattice via NATS and wRPC.

    This initial skeleton defers heavy dependencies and connects lazily.
    It is safe to import and instantiate even if the lattice is not running
    or optional client libraries are not installed.
    """

    name = "wasmcloud_service"

    def __init__(self) -> None:
        # Lazy state placeholders
        self._nats = None  # type: ignore[assignment]
        self._nc = None
        self._wrpc = None  # type: ignore[assignment]
        self._connected = False

        # Read settings
        settings = get_service(ServiceType.SETTINGS_SERVICE, SettingsServiceFactory()).settings
        self._enabled = bool(getattr(settings, "wasmcloud_enabled", False))
        self._nats_url = getattr(settings, "wasmcloud_nats_url", "nats://127.0.0.1:4222")
        self._lattice = getattr(settings, "wasmcloud_lattice", "default")
        self._timeout_ms = int(getattr(settings, "wasmcloud_timeout_ms", 30000))
        self._creds_path = getattr(settings, "wasmcloud_creds_path", None)

    def is_configured(self) -> bool:
        return self._enabled

    def is_available(self) -> bool:
        """Return True if optional deps import and a connection has been attempted."""
        try:
            import nats  # noqa: F401
        except ImportError:
            return False
        return True

    async def connect(self) -> None:
        """Connect to the NATS bus if not already connected.

        This is a best-effort connection. Failures will raise at call time.
        """
        if self._connected:
            return
        try:
            import nats
        except ImportError as exc:
            msg = "nats-py is not installed. Install 'nats-py' to use wasmCloud integration."
            raise RuntimeError(msg) from exc

        connect_kwargs: dict[str, Any] = {"servers": self._nats_url}
        if self._creds_path:
            connect_kwargs["user_credentials"] = self._creds_path

        self._nc = await nats.connect(**connect_kwargs)
        self._connected = True

    async def disconnect(self) -> None:
        if self._nc is not None:
            try:
                await self._nc.drain()
            finally:
                self._nc = None
                self._connected = False

    async def call_component(
        self, component_id: str, operation: str, payload: bytes, timeout_ms: int | None = None
    ) -> bytes:
        """Call a component operation over wRPC via NATS.

        Note: This is a placeholder API surface; the wRPC subject and framing
        will be refined in subsequent iterations.
        """
        if not self._enabled:
            msg = "wasmCloud integration is disabled (wasmcloud_enabled=False)"
            raise RuntimeError(msg)

        await self.connect()
        if self._nc is None:
            msg = "NATS connection not available"
            raise RuntimeError(msg)

        # Provisional subject shape; to be aligned with wasmCloud conventions
        subject = f"wrpc.{self._lattice}.{component_id}.{operation}"
        req_timeout = (timeout_ms if timeout_ms is not None else self._timeout_ms) / 1000.0
        msg = await self._nc.request(subject, payload, timeout=req_timeout)
        return msg.data
