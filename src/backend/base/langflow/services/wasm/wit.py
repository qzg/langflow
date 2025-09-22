from __future__ import annotations

from typing import Any


def _to_wit_type(t: str) -> str:
    t = (t or "string").lower()
    if t in {"string", "str", "text"}:
        return "string"
    if t in {"int", "integer", "s32", "s64"}:
        return "s64"
    if t in {"float", "number", "f32", "f64"}:
        return "float64"
    if t in {"bool", "boolean"}:
        return "bool"
    if t.startswith("list[") and t.endswith("]"):
        inner = t[len("list[") : -1]
        return f"list<{_to_wit_type(inner)}>"
    # default
    return "string"


def synthesize_wit_from_io_schema(io_schema: dict[str, Any], world_name: str = "component") -> str:
    inputs = io_schema.get("inputs") or []
    outputs = io_schema.get("outputs") or []

    def record_fields(items: list[dict[str, Any]], default_name_prefix: str) -> list[tuple[str, str]]:
        fields: list[tuple[str, str]] = []
        for idx, item in enumerate(items):
            name = item.get("name") or f"{default_name_prefix}{idx}"
            typ = _to_wit_type(str(item.get("type") or "string"))
            fields.append((name, typ))
        # deterministic order by name
        fields.sort(key=lambda x: x[0])
        return fields

    in_fields = record_fields(inputs, "in_")
    out_fields = record_fields(outputs, "out_")

    # If single unnamed output with type, allow direct type
    def format_type_or_record(type_name: str, fields: list[tuple[str, str]]) -> tuple[str, str]:
        if len(fields) == 1 and fields[0][0].startswith(type_name):
            # rare: if single field named like type_name0; still produce record for clarity
            pass
        rec_name = type_name.capitalize()
        rec_def = "\n".join([f"  {k}: {v}," for k, v in fields])
        rec_block = f"type {rec_name} = record {{\n{rec_def}\n}};"
        return rec_name, rec_block

    in_type_name, in_block = format_type_or_record("input", in_fields or [("data", "string")])
    out_type_name, out_block = format_type_or_record("output", out_fields or [("data", "string")])

    package = "package langflow:component;\n"
    world = f"world {world_name} {{\n  export process: func(input: {in_type_name}) -> {out_type_name};\n}}"

    return f"{package}\n{in_block}\n\n{out_block}\n\n{world}\n"
