from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from langflow.services.wasm.build import plan_build_command


def test_plan_build_prefers_cargo_component(monkeypatch: pytest.MonkeyPatch):
    # Simulate both cargo and cargo-component present
    def _which(name: str) -> str | None:
        if name == "cargo":
            return "/usr/bin/cargo"
        if name == "cargo-component":
            return "/usr/bin/cargo-component"
        return None

    import shutil as _sh

    monkeypatch.setattr(_sh, "which", _which)

    plan = plan_build_command()
    assert plan.tool.endswith("cargo")
    assert plan.args[:2] == ["component", "build"]


def test_plan_build_fallback_wasi(monkeypatch: pytest.MonkeyPatch):
    # Simulate only cargo present
    def _which(name: str) -> str | None:
        if name == "cargo":
            return "/usr/bin/cargo"
        return None

    import shutil as _sh

    monkeypatch.setattr(_sh, "which", _which)

    plan = plan_build_command()
    assert plan.tool.endswith("cargo")
    assert "--target" in plan.args
    assert "wasm32-wasip2" in plan.args
