from __future__ import annotations

import platform
import plistlib
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
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


def _detect_chrome_on_macos() -> tuple[bool, str | None, str | None]:
    """Detect Chrome (Stable) on macOS and return (installed, version, path)."""
    try:
        app_path = Path("/Applications/Google Chrome.app/Contents/Info.plist")
        if app_path.exists():
            with app_path.open("rb") as f:
                info = plistlib.load(f)
                version = info.get("CFBundleShortVersionString")
                return True, str(version), str(app_path)
    except Exception:  # noqa: BLE001
        return False, None, None
    return False, None, None


def _detect_chrome_generic() -> tuple[bool, str | None, str | None]:
    """Best-effort detection of Chrome/Chromium on non-macOS systems."""
    candidates = [
        "google-chrome",
        "chrome",
        "chromium",
        "chromium-browser",
    ]
    for bin_name in candidates:
        path = shutil.which(bin_name)
        if not path:
            continue
        try:
            completed = subprocess.run(  # noqa: S603
                [path, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        except Exception:  # noqa: S112, BLE001
            continue
        else:
            version = _parse_version(completed.stdout or "")
            return True, version, path
    return False, None, None


async def _run_checks() -> PreflightResponse:
    commands: list[CommandCheck] = [
        CommandCheck(name="node", cmd="node", version_args=["-v"], min_version="20.19.0"),
        CommandCheck(name="npm", cmd="npm", version_args=["-v"], min_version="9.0.0"),
        CommandCheck(name="npx", cmd="npx", version_args=["-v"], min_version=None),
        CommandCheck(name="playwright", cmd="playwright", version_args=["--version"], min_version="1.40.0"),
        CommandCheck(name="claude", cmd="claude", version_args=["--version"], min_version=None),
        CommandCheck(name="warp", cmd="warp", version_args=["--version"], min_version=None),
    ]

    # Run in a worker thread to avoid blocking the event loop
    results = await anyio.to_thread.run_sync(lambda: [_check_command(c) for c in commands])

    # Chrome detection (best-effort)
    if platform.system() == "Darwin":
        installed, version, path = _detect_chrome_on_macos()
    else:
        installed, version, path = _detect_chrome_generic()
    results.append(
        CheckResult(
            name="chrome",
            installed=installed,
            version=version,
            path=path,
            meets_minimum=None,
            minimum_required=None,
            note=None if installed else "Chrome not found. Stable Chrome is recommended for DevTools MCP.",
        )
    )

    # Smoke-check Chrome DevTools MCP server availability via npx (network dependent)
    mcp_ok = False
    mcp_version: str | None = None
    mcp_note: str | None = None
    npx_path = shutil.which("npx")
    if npx_path:

        def _run_mcp_help():
            return subprocess.run(  # noqa: S603
                [npx_path, "-y", "chrome-devtools-mcp@latest", "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
                timeout=15,
            )

        try:
            completed = await anyio.to_thread.run_sync(_run_mcp_help)
            out = completed.stdout or ""
            mcp_ok = completed.returncode == 0 or "chrome-devtools-mcp" in out
            # Try to parse version if present in help banner
            m = re.search(r"chrome-devtools-mcp\D+(v?\d+(?:\.\d+){0,3})", out)
            if m:
                mcp_version = m.group(1)
            if not mcp_ok:
                mcp_note = "Unable to run 'npx chrome-devtools-mcp@latest --help'. Check network and npm auth."
        except Exception as exc:  # noqa: BLE001
            mcp_ok = False
            mcp_note = f"MCP help check failed: {exc}"
    else:
        mcp_note = "npx not found; cannot verify chrome-devtools-mcp."

    results.append(
        CheckResult(
            name="chrome-devtools-mcp",
            installed=mcp_ok,
            version=mcp_version,
            path=None,
            meets_minimum=None,
            minimum_required=None,
            note=mcp_note,
        )
    )

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
