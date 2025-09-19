# wasmCloud Quickstart for Langflow

This quickstart shows how to run a local wasmCloud lattice and invoke a component via Langflow.

Prereqs
- wash CLI (v0.42+)
- wasmCloud host (installed by `wash up`)
- NATS (bundled by `wash up`)
- Optional: nats-py (install with `uv sync --extra wasmcloud`)

1) Start a local lattice (non-destructive)
- wash up
- Check status: wash ctl get hosts/providers/components

2) Configure Langflow
Add to .env (or set via upcoming Settings UI):
- WASMCLOUD_ENABLED=true
- WASMCLOUD_NATS_URL=nats://127.0.0.1:4222
- WASMCLOUD_LATTICE=default
- WASMCLOUD_TIMEOUT_MS=30000
- WASMCLOUD_CREDS_PATH=</path/to/nats.creds> (optional)

3) Build an example component (echo)
- See examples/wasm/echo/ for a minimal WIT world and Rust crate scaffold.
- Build: cargo build --target wasm32-wasi --release (component-model toolchain needed)

4) Invoke from Langflow
- Python (conceptual):
  from langflow.services.deps import get_wasmcloud_service
  svc = get_wasmcloud_service()
  resp = await svc.call_component("<component_id>", "process", b"hello")

Notes
- Use the Test Connection button in the Settings UI (planned) to validate NATS connectivity.
- Capability providers (HTTP/KV/blob/secrets/logging) must be started & linked for components that require them.
