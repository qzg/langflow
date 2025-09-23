# wasmCloud capability providers matrix for Langflow

This matrix captures initial capability providers and how they map to common Langflow node needs. It will evolve as we add concrete bindings and policy defaults.

| Use case | Provider | Contract ID | Typical bindings | Notes |
|---|---|---|---|---|
| Outbound HTTP requests | HTTP Client | wasmcloud:httpclient | none by default; requires outbound network policy | Used by nodes calling external APIs. Honor allowlist/denylist and proxy settings. |
| Key-value storage | KeyValue | wasmcloud:keyvalue | bucket/name; scope | Caching and lightweight state for nodes. |
| Blob/object storage | BlobStore | wasmcloud:blobstore | container/bucket; path prefix | Large artifacts (wasm blobs, logs, datasets). |
| Secrets retrieval | Secrets | wasmcloud:secrets | secret names/scopes | Resolve API keys, tokens at runtime without embedding. |
| Structured logging | Logging | wasmcloud:logging | level, facility | Uniform component logs; surface in UI. |

Conventions
- Bindings are derived from each component's capability manifest (generated + user overrides).
- Default posture is least-privilege. A build or run should fail fast if required bindings are missing.
- Provider choice may vary by deployment (local dev vs. prod). Keep provider-agnostic contracts in manifests.

Open questions
- HTTP: should we model per-domain allowlists in the manifest or defer to zone policy only?
- KV/Blob: naming and retention conventions across environments.
- Secrets: link manifest entries to project/workspace secret stores with scopes.