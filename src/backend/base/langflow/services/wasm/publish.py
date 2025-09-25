from __future__ import annotations

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


def publish_oci(*, wasm_path: Path, oci_ref: str, dry_run: bool = False) -> tuple[PublishPlan, PublishResult]:
    plan = plan_publish(wasm_path=wasm_path, oci_ref=oci_ref)
    if not plan.tool:
        return plan, PublishResult(success=False, error="no OCI tooling (oras/wash) found on PATH")
    if dry_run:
        return plan, PublishResult(success=True, error=None)

    try:
        subprocess.run([plan.tool, *plan.args], check=True)  # noqa: S603
        return plan, PublishResult(success=True, error=None)
    except Exception as exc:  # noqa: BLE001
        return plan, PublishResult(success=False, error=str(exc))
