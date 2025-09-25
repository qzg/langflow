from __future__ import annotations

import json
import re

from .wit_generator import _normalize_ident  # reuse local helper


def parse_world_name(wit_source: str) -> str:
    """Best-effort extraction of the world name from a WIT source string."""
    m = re.search(r"^\s*world\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\{", wit_source, flags=re.MULTILINE)
    if m:
        return m.group(1)
    return "component"


def generate_rust_skeleton(
    *,
    wit_source: str,
    package_name: str = "lf_component",
    world_name: str | None = None,
    func_name: str = "process",
) -> dict[str, str]:
    """Generate a minimal Rust crate skeleton for a component.

    Returns a dict path->content containing Cargo.toml, src/lib.rs, and wit/world.wit.
    The crate is intended for later refinement with wit-bindgen and real logic.
    """
    pkg = _normalize_ident(package_name)
    # Determine names (world currently unused in the M0 stub)
    _ = world_name or parse_world_name(wit_source)
    func_ident = _normalize_ident(func_name)

    cargo_toml = f"""
[package]
name = "{pkg}"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib"]

[dependencies]
wit-bindgen = "0.24.0"
# Add logging, capability helpers, etc. as needed
""".lstrip()

    lib_rs = f"""
//! Auto-generated Rust skeleton for Langflow Wasm component (M0)
//! This is a placeholder implementation and will be completed by the AI porting step.

// The WIT world is expected at: wit/world.wit
// In a real build, wit-bindgen would generate bindings and the exported trait to implement.

#[allow(unused)]
pub fn {func_ident}_stub() {{
    // TODO: implement logic; map inputs/outputs to WIT-generated types
}}
""".lstrip()

    files: dict[str, str] = {
        "Cargo.toml": cargo_toml,
        "src/lib.rs": lib_rs,
        "wit/world.wit": wit_source,
    }
    return files


def encode_crate_files(files: dict[str, str]) -> str:
    """Encode the crate file mapping as a JSON string for storage in ComponentTwin.rust_source."""
    return json.dumps(files)


def decode_crate_files(text: str | None) -> dict[str, str]:
    if not text:
        return {}
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:  # noqa: BLE001
        # If decoding fails, return empty mapping
        return {}
    return {}
