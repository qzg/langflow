# Security UX Notes for Wasm Components (Wassette-inspired)

Goals
- Make capability needs explicit per component via a capability manifest.
- Default-deny posture for network, storage, env, and secrets.
- Provide users with a clear review/override dialog before build/deploy.

Capability manifest (per Component Twin)
- network:
  - allow_domains: ["api.example.com", "*.openai.com"]
  - allow_ips: [] (optional)
- storage:
  - blob_buckets: ["langflow-artifacts", "parity-repro"]
  - kv_namespaces: ["lfx-cache"]
- env:
  - allow_vars: ["LANGFLOW_ENV", "DEBUG"]
- secrets:
  - allow: ["OPENAI_API_KEY", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
- logging:
  - level: info (component-side logging preferences)

UX surfaces
- Node Security dialog: shows proposed manifest (inferred from code + I/O schema) and allows edits.
- Build pipeline uses the manifest to:
  - Persist into Component Twin (capability_manifest field)
  - Emit link definitions for wasmCloud providers
  - Fail fast if required bindings are missing

Developer flow
- Author Python node → infer needs → generate WIT → generate Rust skeleton
- During infer step (#8), propose the capability manifest
- User confirms in UI → manifest persisted → used in build + publish (#9/#10)

Future enhancements
- Runtime enforcement telemetry (violations → incidents)
- Policy presets per deployment (e.g., "offline-only", "no-external-http")
- Guardrails integration for data loss prevention and prompt injection mitigation
