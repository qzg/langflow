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


def build_component(*, wit_source: str, rust_source: str | None, dry_run: bool = False) -> BuildResult:
    plan = plan_build(wit_source=wit_source, rust_source=rust_source)
    if dry_run:
        return BuildResult(built=False, wasm_path=None, logs_path=None, error=None)

    # Attempt to run cargo build; capture logs
    logs_path = plan.workspace / "build.log"
    wasm_out: Path | None = None
    try:
        import subprocess

        with logs_path.open("w") as log:
            # Allow component model toolchains to be configured later. For M0, try a wasi target.
            import shutil

            cargo = shutil.which("cargo")
            if not cargo:
                msg = "cargo not found on PATH"
                raise RuntimeError(msg)
            subprocess.run([cargo, "--version"], check=True, cwd=plan.workspace, stdout=log, stderr=log)  # noqa: S603
            subprocess.run(  # noqa: S603
                [cargo, "build", "--release", "--target", "wasm32-wasi"],
                check=True,
                cwd=plan.workspace,
                stdout=log,
                stderr=log,
            )
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
