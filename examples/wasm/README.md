# Langflow Wasm examples

This directory contains a minimal Component Model example plus build notes. The goal is to prove: (1) a minimal WIT world, (2) a Rust skeleton that compiles to a component .wasm, and (3) compatibility with Wasmtime/wasmCloud.

## Prereqs
- Rust toolchain
- One of:
  - cargo-component (recommended)
  - or wasm-tools + wit-bindgen CLI
- Wasmtime for local runs

On macOS:
- brew install wasmtime wasm-tools
- cargo install cargo-component
- rustup target add wasm32-wasi

## Build (cargo-component)
From `examples/wasm/minimal-component`:

```bash
# If using cargo-component (generates component model artifacts)
cargo component build --release
```

## Build (wasm-tools)
```bash
# 1) Build a core wasm artifact
cargo build --target wasm32-wasi --release

# 2) Wrap as a component using the WIT world
wasm-tools component new target/wasm32-wasi/release/langflow-minimal-component.wasm \
  -o target/release/langflow-minimal-component.component.wasm \
  --adapt wasi_snapshot_preview1=wasi_snapshot_preview1.reactor.wasm \
  --wit ./wit --world component
```

Note: exact flags may change with tool versions; see Wasmtime and wasm-tools docs.

## Run (Wasmtime)
```bash
wasmtime component run target/release/langflow-minimal-component.component.wasm \
  --invoke process -- "hello"
```

Expected: the component echoes the input string.