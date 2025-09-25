# wasmCloud Capability Providers Matrix for Langflow

This document inventories common wasmCloud capability providers and maps them to Langflow use-cases. It also notes bindings that typical components will require.

Key providers
- HTTP Client: outbound HTTP(S) calls from components (fetch data, call APIs)
- Key-Value (KV): small state and caches (e.g., session state, counters)
- Blob/Object Storage: larger artifacts and binaries (e.g., .wasm blobs, logs, datasets)
- Secrets: credential and token retrieval at runtime
- Logging: structured logs out of components

Langflow use-cases → provider requirements
- HTTP tool / web fetch nodes → HTTP Client
- Vector storage adapters (S3/minio) → Blob/Object Storage (or provider-specific)
- Auth-bound calls (OpenAI/Bedrock/etc.) → Secrets
- Intermediate artifacts (parity repro, build logs) → Blob/Object Storage + Logging
- Simple component state (e.g., last-run markers) → KV

Binding notes
- Bindings are driven by per-component capability manifests (see security UX notes). These manifests become link definitions in the lattice.
- Example (conceptual):
  - Component: demo/echo:process
  - Needs: Logging only
  - Bind: logging provider and route stdout/stderr to it

Subject conventions
- wRPC subjects are provisionally shaped as: `wrpc.{lattice}.{component_id}.{operation}`
- This aligns with the Langflow WasmCloudService placeholder and will be refined against upstream wasmCloud conventions.

Local validation steps (quick outline)
- Start lattice: `wash up`
- Build example echo component: see examples/wasm/echo/
- Load component and providers: `wash ctl start component`, `wash ctl start provider`
- Link as required (HTTP/KV/blob/secrets/logging)
- Invoke: use Langflow’s `/api/v1/wasmcloud/invoke` endpoint or Python service wrapper to send a payload and inspect the response
