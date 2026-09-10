from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class MemoryRow(Base):
    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentRow(Base):
    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(100))
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TaskRow(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=50, index=True)
    required_capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), index=True)
    assigned_agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkerRunRow(Base):
    __tablename__ = "worker_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), index=True)
    worker_name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50), index=True)
    external_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SubmittedSetupRow(Base):
    """Backs setup_submission.SetupSubmissionService -- the actual
    approval gate everything downstream depends on. Found unpersisted by
    an external test pass (finding #3): every pending/approved/rejected
    setup lived only in a process-memory dict, silently gone on any
    restart.

    Columns are indexed for exactly the queries SetupSubmissionService
    itself makes (status(), get_pending_approvals(), get_all()); `data`
    holds the complete, real SubmittedSetup Pydantic model as JSON, so a
    read never has to reassemble it from scattered columns -- the indexed
    columns exist for filtering/ordering, not as the source of truth.
    """

    __tablename__ = "submitted_setups"
    approval_request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), index=True)
    decision: Mapped[str] = mapped_column(String(20), index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    data: Mapped[str] = mapped_column(Text)


class DynamicRiskRecordRow(Base):
    """Backs modules.dynamic_risk_engine.DynamicRiskService -- the risk
    sizing step between an approved setup and a tracked position. Same
    finding, same fix as SubmittedSetupRow: in-memory only, gone on
    restart."""

    __tablename__ = "dynamic_risk_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(100), index=True)
    source_key: Mapped[str] = mapped_column(String(200), index=True)
    state: Mapped[str] = mapped_column(String(40), index=True)
    data: Mapped[str] = mapped_column(Text)


class DynamicRiskAuditRow(Base):
    __tablename__ = "dynamic_risk_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    data: Mapped[str] = mapped_column(Text)


class DynamicRiskUsedTokenRow(Base):
    """Replay protection for approval tokens and downstream receipts --
    also previously in-memory only (two plain Python sets). A restart
    right after a token was used, but before this table existed, would
    have silently forgotten it was ever spent: the same approval token
    could then be replayed to approve a second, different risk record.
    Not a hypothetical -- the exact same "process memory only" gap as
    everything else in this finding, just a security property rather
    than a visibility one."""

    __tablename__ = "dynamic_risk_used_tokens"
    token: Mapped[str] = mapped_column(String(200), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # "approval_token" | "downstream_receipt"


class PositionManagementRecordRow(Base):
    __tablename__ = "position_management_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(100), index=True)
    source_key: Mapped[str] = mapped_column(String(200), index=True)
    state: Mapped[str] = mapped_column(String(40), index=True)
    data: Mapped[str] = mapped_column(Text)


class PositionManagementPayloadRow(Base):
    """The original PositionCreate payload, keyed by the resulting
    record's own id -- execute()'s APPLY_RULE command looks up
    payload.exit_rules, a field that lives on the creation payload, not
    the record itself. Previously a second in-memory dict alongside the
    records one; same restart-loses-everything gap."""

    __tablename__ = "position_management_payloads"
    record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    data: Mapped[str] = mapped_column(Text)


class PositionManagementAuditRow(Base):
    __tablename__ = "position_management_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    data: Mapped[str] = mapped_column(Text)


class PositionManagementUsedTokenRow(Base):
    __tablename__ = "position_management_used_tokens"
    token: Mapped[str] = mapped_column(String(200), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # "approval_token" | "downstream_receipt"
