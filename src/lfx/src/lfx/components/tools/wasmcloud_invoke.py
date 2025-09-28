from __future__ import annotations

import base64

from lfx.custom.custom_component.component import Component
from lfx.io import DictInput, IntInput, MultilineInput, Output, StrInput
from lfx.schema.data import Data

# We deliberately import from langflow services to reuse the configured wasmCloud service.
try:
    from langflow.services.deps import get_wasmcloud_service
except ImportError:  # pragma: no cover - fallback for environments without langflow wiring
    get_wasmcloud_service = None  # type: ignore[assignment]


class WasmCloudInvoke(Component):
    """Invoke a wasmCloud component operation over NATS (wRPC).

    Inputs:
      - component_id: hierarchical id (e.g., "acme.greeter")
      - operation: operation verb (e.g., "process")
      - payload_json: JSON payload (preferred)
      - payload_text: Text payload (used if JSON not provided)
      - timeout_ms: optional per-call timeout override (ms)

    Output:
      - result: Data containing the UTF-8 text response if decodable, otherwise base64 bytes under data["b64"].
    """

    display_name: str = "WasmCloud Invoke"
    description: str = "Call a wasmCloud component operation via NATS wRPC."
    documentation: str = "https://wasmcloud.com/docs"  # generic doc link; adjust if needed
    icon = "Cpu"
    name = "WasmCloudInvoke"
    priority = 0

    inputs = [
        StrInput(
            name="component_id",
            display_name="Component ID",
            required=True,
            value="acme.greeter",
            info="Hierarchical id, e.g., 'org.service'",
        ),
        StrInput(
            name="operation",
            display_name="Operation",
            required=True,
            value="process",
            info="Operation verb to call on the component",
        ),
        DictInput(
            name="payload_json",
            display_name="Payload (JSON)",
            required=False,
            value={},
            info="Preferred payload format; takes precedence if provided",
        ),
        MultilineInput(
            name="payload_text",
            display_name="Payload (Text)",
            required=False,
            value="",
            info="Used only when JSON is not provided",
        ),
        IntInput(
            name="timeout_ms",
            display_name="Timeout (ms)",
            required=False,
            value=None,  # type: ignore[arg-type]
            info="Optional per-call timeout override in milliseconds",
        ),
        StrInput(
            name="lattice",
            display_name="Lattice Override",
            required=False,
            value="",
            info="Override lattice for this call; leave blank to use Settings",
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="invoke"),
    ]

    async def invoke(self) -> Data:
        if get_wasmcloud_service is None:
            msg = "wasmCloud service not available in this environment"
            raise RuntimeError(msg)

        svc = get_wasmcloud_service()
        # Preflight
        if not svc.is_configured():
            msg = "wasmCloud integration is disabled (enable it in Settings → Runtime)"
            raise RuntimeError(msg)
        if not svc.is_available():
            msg = "nats-py not installed or unavailable on the server"
            raise RuntimeError(msg)

        # Try a quick connect preflight with 10s timeout
        import asyncio as _asyncio

        try:
            await _asyncio.wait_for(svc.connect(), timeout=10.0)
            await svc.disconnect()
        except Exception as exc:
            msg = f"wasmCloud preflight failed: {exc}"
            raise RuntimeError(msg) from exc

        # Build payload preference: JSON > Text > empty
        payload_bytes: bytes
        if isinstance(self.payload_json, dict) and self.payload_json:
            # Serialize JSON to bytes (utf-8 JSON)
            import orjson

            payload_bytes = orjson.dumps(self.payload_json)
        elif isinstance(self.payload_text, str) and self.payload_text != "":
            payload_bytes = self.payload_text.encode("utf-8")
        else:
            payload_bytes = b""

        timeout_val: int | None
        try:
            timeout_val = int(self.timeout_ms) if self.timeout_ms not in (None, "") else None  # type: ignore[arg-type]
        except (TypeError, ValueError):
            timeout_val = None

        # Perform the call
        data = await svc.call_component(
            self.component_id,
            self.operation,
            payload_bytes,
            timeout_ms=timeout_val,
            lattice_override=(self.lattice or None),
        )

        # Prepare output
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            b64 = base64.b64encode(data).decode("ascii")
            out = Data(value="(binary)")
            # Attach as artifact-like payload
            out.data["b64"] = b64
            self.status = "(binary)"
            return out
        else:
            out = Data(value=text)
            self.status = text
            return out
