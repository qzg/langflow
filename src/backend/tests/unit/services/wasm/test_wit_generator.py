from __future__ import annotations

from langflow.services.wasm.wit_generator import generate_wit


def test_generate_wit_string_in_out():
    io = {
        "inputs": [{"name": "text", "type": "string"}],
        "outputs": [{"name": "text", "type": "string"}],
    }
    wit = generate_wit(io, world_name="echo", func_name="process")
    assert "world echo" in wit
    assert "type Input = record" in wit
    assert "type Output = record" in wit
    assert "text: string" in wit
    assert "export process: func(input: Input) -> Output" in wit


def test_generate_wit_array_and_object():
    io = {
        "inputs": [
            {"name": "values", "type": "array", "items": {"type": "number"}},
            {
                "name": "cfg",
                "type": "object",
                "properties": {"a": {"type": "string"}, "b": {"type": "boolean"}},
            },
        ],
        "outputs": [{"name": "ok", "type": "boolean"}],
    }
    wit = generate_wit(io)
    assert "values: list<float64>" in wit
    # Inline object becomes a record for M0
    assert "cfg: record" in wit or "cfg: string" in wit
    assert "ok: bool" in wit
