from __future__ import annotations

import hashlib
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
    validated_component: bool
    wrapped: bool
    plan_tool: str | None
    plan_args: list[str] | None
    digest: str | None
    size: int | None
    tool_versions: dict[str, str]


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


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_component(*, wit_source: str, rust_source: str | None, dry_run: bool = False) -> BuildResult:
    plan = plan_build(wit_source=wit_source, rust_source=rust_source)
    if dry_run:
        return BuildResult(
            built=False,
            wasm_path=None,
            logs_path=None,
            error=None,
            validated_component=False,
            wrapped=False,
            plan_tool=None,
            plan_args=None,
            digest=None,
            size=None,
            tool_versions={},
        )

    # Attempt to run the planned build; capture logs
    logs_path = plan.workspace / "build.log"
    wasm_out: Path | None = None
    tool_versions: dict[str, str] = {}
    try:
        import shutil as _sh
        import subprocess

        cmd_plan = plan_build_command()
        with logs_path.open("w") as log:
            if not cmd_plan.tool:
                msg = "cargo not found on PATH"
                raise RuntimeError(msg)

            # Log versions
            try:
                out = subprocess.run(  # noqa: S603
                    [cmd_plan.tool, "--version"],
                    check=True,
                    cwd=plan.workspace,
                    capture_output=True,
                )
                tool_versions["cargo"] = out.stdout.decode().strip() if getattr(out, "stdout", None) else ""
            except (subprocess.CalledProcessError, OSError):
                tool_versions["cargo"] = "unknown"

            # Run build
            subprocess.run(  # noqa: S603
                [cmd_plan.tool, *cmd_plan.args],
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
                validated_component=False,
                wrapped=False,
                plan_tool=cmd_plan.tool,
                plan_args=cmd_plan.args,
                digest=None,
                size=None,
                tool_versions=tool_versions,
            )

        # Validate it's a Component; if not, and wasm-tools is available, wrap core WASM → Component
        wasm_tools = _sh.which("wasm-tools")
        validated_component = False
        wrapped = False
        if wasm_tools:
            # Record wasm-tools version
            try:
                out = subprocess.run(  # noqa: S603
                    [wasm_tools, "--version"],
                    check=True,
                    cwd=plan.workspace,
                    capture_output=True,
                )
                tool_versions["wasm-tools"] = out.stdout.decode().strip() if getattr(out, "stdout", None) else ""
            except (subprocess.CalledProcessError, OSError):
                tool_versions["wasm-tools"] = "unknown"
            try:
                subprocess.run(  # noqa: S603
                    [wasm_tools, "component", "wit", str(wasm_out)],
                    check=True,
                    cwd=plan.workspace,
                    capture_output=True,
                )
                validated_component = True
            except subprocess.CalledProcessError:
                # Attempt wrap
                comp_out = wasm_out.with_suffix(".component.wasm")
                try:
                    subprocess.run(  # noqa: S603
                        [wasm_tools, "component", "new", str(wasm_out), "-o", str(comp_out)],
                        check=True,
                        cwd=plan.workspace,
                        capture_output=True,
                    )
                    wasm_out = comp_out
                    wrapped = True
                    # Verify again
                    try:
                        subprocess.run(  # noqa: S603
                            [wasm_tools, "component", "wit", str(wasm_out)],
                            check=True,
                            cwd=plan.workspace,
                            capture_output=True,
                        )
                        validated_component = True
                    except (subprocess.CalledProcessError, OSError):
                        validated_component = False
                except (subprocess.CalledProcessError, OSError):
                    wrapped = False

        # Compute digest and size
        digest = _sha256_file(wasm_out)
        try:
            size = wasm_out.stat().st_size
        except OSError:
            size = None

        return BuildResult(
            built=True,
            wasm_path=wasm_out,
            logs_path=logs_path,
            error=None,
            validated_component=validated_component,
            wrapped=wrapped,
            plan_tool=cmd_plan.tool,
            plan_args=cmd_plan.args,
            digest=digest,
            size=size,
            tool_versions=tool_versions,
        )

    except Exception as exc:  # noqa: BLE001
        # Write error if not already; ignore secondary failures.
        from contextlib import suppress

        with suppress(Exception):
            if not logs_path.exists():
                logs_path.write_text(str(exc))
        return BuildResult(
            built=False,
            wasm_path=None,
            logs_path=logs_path if logs_path.exists() else None,
            error=str(exc),
            validated_component=False,
            wrapped=False,
            plan_tool=None,
            plan_args=None,
            digest=None,
            size=None,
            tool_versions={},
        )
