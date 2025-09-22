from __future__ import annotations

import os
import shutil
import tempfile
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import anyio
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


async def _write_file(flow_id: UUID, name: str, data: bytes) -> str:
    storage = get_storage_service()
    await storage.save_file(str(flow_id), name, data)
    return f"local://{flow_id}/{name}"


async def _finalize_with_logs(twin: ComponentTwin, session: AsyncSession, *, ok: bool, logs_text: str) -> BuildResult:
    try:
        logs_name = f"twin_{twin.id}.log"
        logs_uri = await _write_file(twin.flow_id, logs_name, logs_text.encode("utf-8"))
    except Exception:
        logs_uri = None

    if ok:
        twin.build_status = "built"
    else:
        twin.build_status = "error"
    twin.build_logs_uri = logs_uri
    twin.updated_at = datetime.now(timezone.utc)
    session.add(twin)
    await session.commit()
    await session.refresh(twin)
    return BuildResult(ok=ok, artifact_uri=twin.wasm_blob, logs_uri=logs_uri, message=("built" if ok else "error"))


async def build_twin(session: AsyncSession, twin: ComponentTwin) -> BuildResult:
    """Build a ComponentTwin into a Wasm artifact using the Rust toolchain if available.

    Build strategy:
    - Ensure a WIT source exists (synthesize from io_schema when needed) and persist it
    - If cargo is available, scaffold a minimal crate and compile to wasm32-wasi
    - Save the resulting .wasm and build logs via StorageService
    - On failure or missing toolchain, return an error (caller will mark twin as error)

    Note: This produces a classic WASI module by default. The runtime will attempt
    component-model instantiation first and fall back to module instantiation.
    """
    logs: list[str] = []
    try:
        # Ensure we have a WIT source
        wit = twin.wit_source
        if not wit:
            if twin.io_schema:
                wit = synthesize_wit_from_io_schema(twin.io_schema, world_name="component")
                twin.wit_source = wit
            else:
                msg = "No wit_source or io_schema available to build from"
                logs.append(msg)
                return await _finalize_with_logs(twin, session, ok=False, logs_text="\n".join(logs))

        # Persist WIT (for inspection)
        wit_name = f"twin_{twin.id}.wit"
        wit_uri = await _write_file(twin.flow_id, wit_name, wit.encode("utf-8"))
        logs.append(f"WIT saved at: {wit_uri}")

        cargo = shutil.which("cargo")
        if not cargo:
            msg = "cargo not found in PATH; cannot perform real build"
            logs.append(msg)
            return await _finalize_with_logs(twin, session, ok=False, logs_text="\n".join(logs))

        # Prepare crate in a temporary working directory
        with tempfile.TemporaryDirectory(prefix=f"ctwin_{twin.id}_") as tmpdir:
            crate_dir = tmpdir
            src_dir = os.path.join(crate_dir, "src")
            os.makedirs(src_dir, exist_ok=True)

            # Cargo.toml
            cargo_toml = textwrap.dedent(
                f"""
                [package]
                name = "ctwin_{twin.id}"
                version = "0.1.0"
                edition = "2021"

                [lib]
                crate-type = ["cdylib"]
                path = "src/lib.rs"

                [profile.release]
                opt-level = "s"
                lto = true
                codegen-units = 1
                panic = "abort"
                strip = true
                """
            ).strip()
            with open(os.path.join(crate_dir, "Cargo.toml"), "w", encoding="utf-8") as f:
                f.write(cargo_toml)

            # lib.rs: use provided rust_source or a minimal stub
            lib_rs = (
                twin.rust_source
                or textwrap.dedent(
                    """
                #[no_mangle]
                pub extern "C" fn process() {}
                """
                ).strip()
            )
            with open(os.path.join(src_dir, "lib.rs"), "w", encoding="utf-8") as f:
                f.write(lib_rs + "\n")

            # Ensure wasm32-wasi target is installed
            rustup = shutil.which("rustup")
            if rustup:
                try:
                    cp = await anyio.run_process(
                        [rustup, "target", "add", "wasm32-wasi"],
                        cwd=crate_dir,
                        check=False,
                        stdout=anyio.subprocess.PIPE,
                        stderr=anyio.subprocess.PIPE,
                    )
                    if cp.stdout:
                        logs.append(cp.stdout.decode())
                    if cp.stderr:
                        logs.append(cp.stderr.decode())
                except Exception as exc:  # noqa: BLE001
                    logs.append(f"warning: failed to add wasm32-wasi target: {exc}")

            # Build
            try:
                cp = await anyio.run_process(
                    [cargo, "build", "--release", "--target", "wasm32-wasi"],
                    cwd=crate_dir,
                    check=False,
                    stdout=anyio.subprocess.PIPE,
                    stderr=anyio.subprocess.PIPE,
                )
                stdout = cp.stdout.decode() if cp.stdout else ""
                stderr = cp.stderr.decode() if cp.stderr else ""
                logs.append(stdout)
                logs.append(stderr)

                if cp.returncode != 0:
                    return await _finalize_with_logs(twin, session, ok=False, logs_text="\n".join(logs))
            except Exception as exc:  # noqa: BLE001
                logs.append(f"cargo build failed: {exc}")
                return await _finalize_with_logs(twin, session, ok=False, logs_text="\n".join(logs))

            # Locate output file
            # Cargo names artifact after package with '-' converted to '_'
            pkg_name = f"ctwin_{twin.id}".replace("-", "_")
            built_path = os.path.join(crate_dir, "target", "wasm32-wasi", "release", f"{pkg_name}.wasm")

            # If still missing, try scanning directory
            if not os.path.exists(built_path):
                rel_dir = os.path.join(crate_dir, "target", "wasm32-wasi", "release")
                try:
                    candidates = [p for p in os.listdir(rel_dir) if p.endswith(".wasm")]
                    if candidates:
                        built_path = os.path.join(rel_dir, candidates[0])
                except Exception:  # noqa: BLE001
                    pass

            if not os.path.exists(built_path):
                logs.append("could not locate built wasm artifact")
                return await _finalize_with_logs(twin, session, ok=False, logs_text="\n".join(logs))

            # Save artifact
            with open(built_path, "rb") as f:
                artifact_bytes = f.read()
            wasm_name = f"twin_{twin.id}.wasm"
            artifact_uri = await _write_file(twin.flow_id, wasm_name, artifact_bytes)
            logs.append(f"Artifact saved at: {artifact_uri}")

        # Success
        twin.build_status = "built"
        twin.updated_at = datetime.now(timezone.utc)
        session.add(twin)
        await session.commit()
        await session.refresh(twin)

        # Write logs last (not critical if fails)
        logs_name = f"twin_{twin.id}.log"
        logs_uri = await _write_file(twin.flow_id, logs_name, "\n".join(logs).encode("utf-8"))
        twin.build_logs_uri = logs_uri
        twin.wasm_blob = artifact_uri
        session.add(twin)
        await session.commit()
        await session.refresh(twin)

        return BuildResult(ok=True, artifact_uri=artifact_uri, logs_uri=logs_uri, message="built")
    except Exception as exc:  # noqa: BLE001
        await logger.aexception(f"ComponentTwin build failed: {exc!s}")
        # Attempt to persist logs if any
        try:
            logs_name = f"twin_{twin.id}.log"
            logs_uri = await _write_file(twin.flow_id, logs_name, "\n".join(logs + [str(exc)]).encode("utf-8"))
        except Exception:
            logs_uri = None
        return BuildResult(ok=False, artifact_uri=None, logs_uri=logs_uri, message=str(exc))
