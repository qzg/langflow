# wasmCloud Capability Providers Matrix (initial)

This document maps commonly used capability providers to Langflow use-cases.

Providers
- logging: structured logs from components
- httpclient: outbound HTTP requests (LLM APIs, data fetch)
- keyvalue: small state / caching
- blobstore: large artifacts (build logs, wasm blobs)
- secrets: runtime secret injection

Typical bindings
- httpclient: allow-list base URLs/domains; method restrictions when feasible
- keyvalue: per-component namespace to avoid collisions
- blobstore: scoped buckets/paths per project/flow
- secrets: minimal set per component; avoid sharing across flows
- logging: standard metadata (component_id, flow_id, request_id)

Notes
- Provider versions should be pinned for reproducibility.
- Link definitions must be applied at deploy time (wash app manifest or CLI).
