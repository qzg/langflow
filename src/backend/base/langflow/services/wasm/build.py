from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .rust_skeleton import decode_crate_files, generate_rust_skeleton


@dataclass
class BuildPlan:
    workspace: Path
    files: dict[str, str]


@dataclass
class BuildCommandPlan:
    tool: str
    args: list[str]


@dataclass
class BuildResult:
    built: bool
    wasm_path: Path | None
    logs_path: Path | None
    error: str | None


_WORLD_RE = re.compile(r"^\s*world\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\{", re.MULTILINE)


def _materialize_workspace(files: dict[str, str], base_dir: Path) -> None:
    for rel, content in files.items():
        p = base_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def plan_build(*, wit_source: str, rust_source: str | None) -> BuildPlan:
    tmpdir = Path(tempfile.mkdtemp(prefix="lf_wasm_build_"))
    files = decode_crate_files(rust_source)
    if not files:
        # If no rust_source yet, generate a skeleton
        files = generate_rust_skeleton(wit_source=wit_source)
    _materialize_workspace(files, tmpdir)
    return BuildPlan(workspace=tmpdir, files=files)


def plan_build_command() -> BuildCommandPlan:
    """Return the preferred build command plan for producing a Wasm artifact.

    Preference order (M0):
    1) cargo component build --release (if cargo and cargo-component are on PATH)
    2) cargo build --release --target wasm32-wasip2 (fallback aligned with Component Model)
    If neither is available, returns tool="" and args=[].
    """
    import shutil

    cargo = shutil.which("cargo")
    cargo_component_bin = shutil.which("cargo-component")
    if cargo and cargo_component_bin:
        return BuildCommandPlan(tool=cargo, args=["component", "build", "--release"])  # uses cargo subcommand
    if cargo:
        return BuildCommandPlan(tool=cargo, args=["build", "--release", "--target", "wasm32-wasip2"])  # fallback
    return BuildCommandPlan(tool="", args=[])


def build_component(*, wit_source: str, rust_source: str | None, dry_run: bool = False) -> BuildResult:
    plan = plan_build(wit_source=wit_source, rust_source=rust_source)
    if dry_run:
        return BuildResult(built=False, wasm_path=None, logs_path=None, error=None)

    # Attempt to run the planned build; capture logs
    logs_path = plan.workspace / "build.log"
    wasm_out: Path | None = None
    try:
        import subprocess

        with logs_path.open("w") as log:
            cmd_plan = plan_build_command()
            if not cmd_plan.tool:
                msg = "cargo not found on PATH"
                raise RuntimeError(msg)

            # Log versions
            subprocess.run([cmd_plan.tool, "--version"], check=True, cwd=plan.workspace, stdout=log, stderr=log)  # noqa: S603
            # Run build
            subprocess.run([cmd_plan.tool, *cmd_plan.args], check=True, cwd=plan.workspace, stdout=log, stderr=log)  # noqa: S603
        # Heuristic: find a .wasm under target directory
        for p in (plan.workspace / "target").rglob("*.wasm"):
            wasm_out = p
            break
        if not wasm_out:
            return BuildResult(
                built=False,
                wasm_path=None,
                logs_path=logs_path,
                error=".wasm not found after build",
            )

        # Validate it's a Component; if not, and wasm-tools is available, wrap core WASM → Component
        import shutil as _sh

        wasm_tools = _sh.which("wasm-tools")
        if wasm_tools:
            try:
                subprocess.run(  # noqa: S603
                    [wasm_tools, "component", "wit", str(wasm_out)],
                    check=True,
                    cwd=plan.workspace,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                # Attempt wrap
                comp_out = wasm_out.with_suffix(".component.wasm")
                with logs_path.open("a") as log:
                    log.write("\n[wrap] core WASM detected, wrapping into Component via wasm-tools component new\n")
                subprocess.run(  # noqa: S603
                    [wasm_tools, "component", "new", str(wasm_out), "-o", str(comp_out)],
                    check=True,
                    cwd=plan.workspace,
                )
                wasm_out = comp_out

        return BuildResult(built=True, wasm_path=wasm_out, logs_path=logs_path, error=None)
    except Exception as exc:  # noqa: BLE001
        # Write error if not already; ignore secondary failures.
        if not logs_path.exists():
            import contextlib

            with contextlib.suppress(Exception):
                logs_path.write_text(str(exc))
        return BuildResult(
            built=False,
            wasm_path=None,
            logs_path=logs_path if logs_path.exists() else None,
            error=str(exc),
        )
