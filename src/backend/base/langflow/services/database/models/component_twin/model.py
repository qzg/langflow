from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


class ComponentTwinBase(SQLModel):
    """Represents a persisted twin of a component across build artifacts.

    Stores source materials and build/provenance metadata for Python→WIT→Rust→Wasm pipeline.
    """

    # Identity within a flow/component graph
    flow_id: UUID = Field(foreign_key="flow.id", index=True)
    component_id: str = Field(index=True, description="Graph/component identifier within the flow")

    # Provenance and source materials
    python_hash: str | None = Field(default=None, index=True, description="Content hash of Python source")
    python_source: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    io_schema: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    wit_source: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    rust_source: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # Build outputs and artifacts
    wasm_blob: str | None = Field(default=None, description="URI or storage path to the built Wasm component artifact")
    capability_manifest: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    build_status: str = Field(
        default="stale",
        index=True,
        description="stale | building | built | error",
    )
    build_logs_uri: str | None = Field(default=None, description="URI/path to build logs artifact")

    # Verification
    last_verified_at: datetime | None = Field(default=None, nullable=True)
    determinism_mode: str | None = Field(default=None, description="e.g., strict | relaxed | nondet")
    parity_metrics: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ComponentTwin(ComponentTwinBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "component_twin"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
