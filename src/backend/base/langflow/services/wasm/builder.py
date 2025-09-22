from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from lfx.log.logger import logger
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.component_twin.model import ComponentTwin
from langflow.services.deps import get_storage_service
from langflow.services.wasm.wit import synthesize_wit_from_io_schema


@dataclass
class BuildResult:
    ok: bool
    artifact_uri: str | None
    logs_uri: str | None
    message: str


_MAGIC_WASM = b"\x00asm\x01\x00\x00\x00"  # minimal header (not a runnable component)


async def _write_file(flow_id: UUID, name: str, data: bytes) -> str:
    storage = get_storage_service()
    await storage.save_file(str(flow_id), name, data)
    # We use a local URI scheme to reference files saved via StorageService
    return f"local://{flow_id}/{name}"


async def build_twin(session: AsyncSession, twin: ComponentTwin) -> BuildResult:
    """Build a ComponentTwin into a Wasm artifact.

    This is a minimal, toolchain-light builder:
    - Ensures a WIT source exists (synthesizes from io_schema when needed)
    - Writes the WIT to storage
    - Produces a placeholder .wasm artifact (valid header only) so downstream plumbing
      can be exercised without requiring cargo/wasmtime toolchain on CI
    - Emits a simple build log
    """
    try:
        # Ensure we have a WIT source
        wit = twin.wit_source
        if not wit:
            if twin.io_schema:
                wit = synthesize_wit_from_io_schema(twin.io_schema, world_name="component")
                twin.wit_source = wit
            else:
                msg = "No wit_source or io_schema available to build from"
                return BuildResult(ok=False, artifact_uri=None, logs_uri=None, message=msg)

        # Persist WIT
        wit_name = f"twin_{twin.id}.wit"
        wit_uri = await _write_file(twin.flow_id, wit_name, wit.encode("utf-8"))

        # Produce a very small placeholder wasm artifact so the pipeline is exercised
        # Include base64 of WIT in a custom section-like payload to make the file non-trivial
        payload = base64.b64encode(wit.encode("utf-8"))
        wasm_bytes = _MAGIC_WASM + b"\x00" + payload[:1024]  # keep it small
        wasm_name = f"twin_{twin.id}.wasm"
        artifact_uri = await _write_file(twin.flow_id, wasm_name, wasm_bytes)

        # Create basic logs
        logs_text = (
            f"Build succeeded (placeholder builder)\nWIT saved at: {wit_uri}\nArtifact saved at: {artifact_uri}\n"
        )
        logs_name = f"twin_{twin.id}.log"
        logs_uri = await _write_file(twin.flow_id, logs_name, logs_text.encode("utf-8"))

        # Update record
        twin.build_status = "built"
        twin.build_logs_uri = logs_uri
        twin.wasm_blob = artifact_uri
        twin.updated_at = datetime.now(timezone.utc)
        session.add(twin)
        await session.commit()
        await session.refresh(twin)

        return BuildResult(ok=True, artifact_uri=artifact_uri, logs_uri=logs_uri, message="built")
    except Exception as exc:  # noqa: BLE001
        await logger.aexception(f"ComponentTwin build failed: {exc!s}")
        return BuildResult(ok=False, artifact_uri=None, logs_uri=None, message=str(exc))
