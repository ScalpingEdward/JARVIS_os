from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ReconciliationState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    PENDING = "pending"
    MATCHED = "matched"
    DRIFT_DETECTED = "drift-detected"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    CORRECTION_QUEUED = "correction-queued"
    RESOLVED = "resolved"
    FAILED = "failed"
    ARCHIVED = "archived"


class DriftSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class PositionSnapshot(BaseModel):
    position_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    side: Literal["buy", "sell"]
    volume: float = Field(gt=0)
    entry_price: float = Field(gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)


class BrokerSnapshot(BaseModel):
    snapshot_id: str = Field(min_length=1)
    account_ref: str = Field(min_length=1)
    balance: float
    equity: float
    margin_used: float = Field(ge=0)
    positions: list[PositionSnapshot] = Field(default_factory=list)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def unique_positions(self):
        ids = [item.position_id for item in self.positions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate position id")
        return self


class ReconciliationCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    runtime_record_id: str = Field(min_length=1)
    command_record_ids: list[str] = Field(min_length=1)
    expected_snapshot: BrokerSnapshot
    broker_snapshot: BrokerSnapshot
    upstream_evidence_verified: bool = False
    risk_brain_blocked: bool = False
    balance_tolerance: float = Field(default=0.01, ge=0)
    equity_tolerance: float = Field(default=0.01, ge=0)
    volume_tolerance: float = Field(default=0.0001, ge=0)


class DriftItem(BaseModel):
    field: str
    expected: str
    actual: str
    severity: DriftSeverity


class ReconciliationAction(BaseModel):
    action: Literal["approve", "queue-correction", "resolve", "fail", "archive"]
    actor_id: str = Field(min_length=1)
    approval_token: str | None = None
    receipt_id: str | None = None
    reason: str | None = None


class ReconciliationRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    runtime_record_id: str
    command_record_ids: list[str]
    expected_snapshot: BrokerSnapshot
    broker_snapshot: BrokerSnapshot
    drifts: list[DriftItem] = Field(default_factory=list)
    state: ReconciliationState
    risk_brain_blocked: bool
    upstream_evidence_verified: bool
    approval_token_hash: str | None = None
    last_receipt_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEvent(BaseModel):
    event_id: str
    record_id: str
    workspace_id: str
    action: str
    actor_id: str
    state: ReconciliationState
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
