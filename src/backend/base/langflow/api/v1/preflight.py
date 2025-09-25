from __future__ import annotations

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

import anyio
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["Preflight"])


@dataclass
class CommandCheck:
    name: str
    cmd: str
    version_args: list[str]
    min_version: str | None = None


class CheckResult(BaseModel):
    name: str
    installed: bool
    version: str | None = None
    path: str | None = None
    meets_minimum: bool | None = None
    minimum_required: str | None = None
    note: str | None = None


class PreflightResponse(BaseModel):
    ok: bool
    system: dict[str, Any] = Field(default_factory=dict)
    checks: list[CheckResult]
    missing: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _parse_version(raw: str) -> str:
    # Extract first version-like token, e.g., 'v20.11.0' or '1.41.2'
    match = re.search(r"(v?\d+(?:\.\d+){0,3})", raw)
    return match.group(1) if match else raw.strip()


VERSION_PARTS = 3


def _compare_versions(v1: str, v2: str) -> int:
    def to_tuple(v: str):
        v = v.lstrip("v")
        parts = [int(p) for p in re.findall(r"\d+", v)[:VERSION_PARTS]]
        while len(parts) < VERSION_PARTS:
            parts.append(0)
        return tuple(parts)

    a = to_tuple(v1)
    b = to_tuple(v2)
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def _check_command(cmd: CommandCheck) -> CheckResult:
    path = shutil.which(cmd.cmd)
    installed = path is not None
    version: str | None = None
    meets_minimum: bool | None = None

    if installed:
        try:
            completed = subprocess.run(  # noqa: S603
                [cmd.cmd, *cmd.version_args],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            version = _parse_version(completed.stdout or "")
        except Exception:  # noqa: BLE001
            version = None

    if cmd.min_version and version:
        meets_minimum = _compare_versions(version, cmd.min_version) >= 0

    note = None
    if cmd.name == "warp" and not installed:
        note = "Warp CLI not found. Warp is primarily a macOS app; CLI integration may be optional."
    if cmd.name == "claude" and not installed:
        note = "Claude CLI not found. Install via `pipx install anthropic` or vendor instructions if required."

    return CheckResult(
        name=cmd.name,
        installed=installed,
        version=version,
        path=path,
        meets_minimum=meets_minimum,
        minimum_required=cmd.min_version,
        note=note,
    )


async def _run_checks() -> PreflightResponse:
    commands: list[CommandCheck] = [
        CommandCheck(name="node", cmd="node", version_args=["-v"], min_version="18.0.0"),
        CommandCheck(name="npm", cmd="npm", version_args=["-v"], min_version="9.0.0"),
        CommandCheck(name="npx", cmd="npx", version_args=["-v"], min_version=None),
        CommandCheck(name="playwright", cmd="playwright", version_args=["--version"], min_version="1.40.0"),
        CommandCheck(name="claude", cmd="claude", version_args=["--version"], min_version=None),
        CommandCheck(name="warp", cmd="warp", version_args=["--version"], min_version=None),
    ]

    # Run in a worker thread to avoid blocking the event loop
    results = await anyio.to_thread.run_sync(lambda: [_check_command(c) for c in commands])

    missing = [r.name for r in results if not r.installed]
    warnings: list[str] = []

    for r in results:
        if r.meets_minimum is False and r.minimum_required:
            warnings.append(
                f"{r.name} version {r.version} < minimum required {r.minimum_required}. Consider upgrading."
            )
        if r.note:
            warnings.append(r.note)

    system = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "python_version": platform.python_version(),
        "machine": platform.machine(),
    }

    ok = len(missing) == 0 and all(r.meets_minimum is not False for r in results)

    return PreflightResponse(ok=ok, system=system, checks=results, missing=missing, warnings=warnings)


@router.get("/preflight", response_model=PreflightResponse)
async def get_preflight() -> PreflightResponse:
    """Perform environment preflight checks for development tooling.

    Checks for availability and versions of Node.js, npm, npx, Playwright, and optional CLIs
    such as Claude and Warp. Returns structured results suitable for UI display.
    """
    return await _run_checks()
