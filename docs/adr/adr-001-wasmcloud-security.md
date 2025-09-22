# ADR: Security posture for wasmCloud integration

Status: Draft

Context
- Components run with explicit capabilities (httpclient, keyvalue, blobstore, secrets, logging).
- We must define default policies for outbound network, data egress, and secret scope.

Decision (initial)
- Outbound HTTP: allow-list domains via config; disallow wildcard in production.
- Secrets: write-only UI; mount at runtime with least privilege; per-component scope.
- Data egress: blobstore paths scoped by project/flow; enforce size limits.
- Observability: standard logging fields; avoid secret materialization in logs.
- Determinism: document determinism modes; enable parity checks against Python.

Consequences
- Safer defaults; clearer review UX in forthcoming Guardian/Settings pages.
- Slight friction for new endpoints until allow-list is curated.

Next steps
- Implement UI affordances for policies; link to provider bindings.
- Encode policies in deployment manifests (wash app or equivalent).
