from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class PublishPlan:
    tool: str
    args: list[str]


def plan_publish(*, wasm_path: Path, oci_ref: str) -> PublishPlan:
    """Plan an OCI publish command using available tooling (oras preferred).

    If neither tool is found, returns a plan with tool="" and args=[] to signal inability.
    """
    oras = shutil.which("oras")
    if oras:
        # oras push <ref> <file>:application/wasm
        return PublishPlan(tool=oras, args=["push", oci_ref, f"{wasm_path}:application/wasm"])
    wash = shutil.which("wash")
    if wash:
        # wash reg push <ref> <file>
        return PublishPlan(tool=wash, args=["reg", "push", oci_ref, str(wasm_path)])
    return PublishPlan(tool="", args=[])


@dataclass
class PublishResult:
    success: bool
    error: str | None
    digest: str | None
    size: int | None


def _file_sha256(path: str) -> str:
    from pathlib import Path

    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def publish_oci(*, wasm_path: Path, oci_ref: str, dry_run: bool = False) -> tuple[PublishPlan, PublishResult]:
    plan = plan_publish(wasm_path=wasm_path, oci_ref=oci_ref)
    if not plan.tool:
        return plan, PublishResult(
            success=False,
            error="no OCI tooling (oras/wash) found on PATH",
            digest=None,
            size=None,
        )

    # In dry-run, do not require the file to exist; compute metadata only if available
    if dry_run:
        size: int | None = None
        digest: str | None = None
        try:
            size = wasm_path.stat().st_size
            digest = _file_sha256(str(wasm_path))
        except OSError:
            # Missing file is acceptable in dry-run mode
            pass
        return plan, PublishResult(success=True, error=None, digest=digest, size=size)

    # Real publish: prefer to compute metadata if file exists; don't fail if missing in tests
    try:
        fsize = wasm_path.stat().st_size
        fdigest = _file_sha256(str(wasm_path))
    except OSError:
        fsize = None
        fdigest = None

    try:
        subprocess.run([plan.tool, *plan.args], check=True)  # noqa: S603
        return plan, PublishResult(success=True, error=None, digest=fdigest, size=fsize)
    except Exception as exc:  # noqa: BLE001
        return plan, PublishResult(success=False, error=str(exc), digest=fdigest, size=fsize)
