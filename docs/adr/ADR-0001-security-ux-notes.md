# ADR-0001: Security UX notes for Wasm components (Wassette-inspired)

Date: 2025-09-23
Status: Draft
Related: #3

## Context
We are introducing Wasm components that run under a lattice with capability providers. Users need visibility and control over what each component can access (network, storage, environment, secrets, logging).

## Decision
1. Default-deny posture with explicit capability manifests per component.
2. Provide a Security dialog on each node to review and override proposed capabilities before build/run.
3. Manifest sources: static analysis + node metadata → proposal; user edits → authoritative.
4. Enforce at build time (bindings required) and runtime (policy + lattice bindings).

## UX elements
- Network: domain/IP allowlist + method constraints (GET/POST). Optional proxy.
- Storage: KV/Blob scopes (buckets/paths) with read/write flags.
- Env: explicit env var passthrough list; no wildcards by default.
- Secrets: named references resolved at runtime; scopes (project/user).
- Logging: default level and redaction hints for PII.

## Consequences
- Safer defaults; more friction initially when capabilities are missing.
- Deterministic builds via manifests checked into the Component Twin.
- Clear audit trail for overrides.

## Follow-ups
- Define manifest schema in the Component Twin.
- Add validators and UI affordances for common pitfalls (e.g., wildcard network).
- Connect to provider-specific policies at deployment time.