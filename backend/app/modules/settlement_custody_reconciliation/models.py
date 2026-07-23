from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class SettlementState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    EVALUATED = "evaluated"
    RECONCILIATION_PROPOSED = "reconciliation-proposed"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    SETTLING = "settling"
    RECONCILING = "reconciling"
    RECONCILED = "reconciled"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class SettlementStatus(str, Enum):
    PENDING = "pending"
    SETTLED = "settled"
    FAILED = "failed"
    REVERSED = "reversed"


class CustodyPosition(BaseModel):
    position_id: str = Field(min_length=1, max_length=180)
    account_id: str = Field(min_length=1, max_length=180)
    custodian_id: str = Field(min_length=1, max_length=180)
    asset: str = Field(min_length=1, max_length=40)
    internal_quantity: float
    external_quantity: float
    tolerance: float = Field(default=0, ge=0)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SettlementItem(BaseModel):
    settlement_id: str = Field(min_length=1, max_length=180)
    provider_id: str = Field(min_length=1, max_length=180)
    source_account_id: str = Field(min_length=1, max_length=180)
    target_account_id: str = Field(min_length=1, max_length=180)
    asset: str = Field(min_length=1, max_length=40)
    amount: float = Field(gt=0)
    expected_fee: float = Field(default=0, ge=0)
    actual_fee: float | None = Field(default=None, ge=0)
    status: SettlementStatus = SettlementStatus.PENDING
    external_reference: str | None = Field(default=None, max_length=240)
    evidence_refs: list[str] = Field(min_length=1)


class ReconciliationInstruction(BaseModel):
    instruction_id: str = Field(min_length=1, max_length=180)
    position_id: str = Field(min_length=1, max_length=180)
    expected_delta: float
    rationale: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(min_length=1)


class SettlementCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    treasury_record_id: str = Field(min_length=1, max_length=180)
    ledger_name: str = Field(min_length=1, max_length=240)
    positions: list[CustodyPosition] = Field(min_length=1)
    settlements: list[SettlementItem] = Field(default_factory=list)
    instructions: list[ReconciliationInstruction] = Field(default_factory=list)
    minimum_confidence: float = Field(default=0.8, ge=0, le=1)
    maximum_unreconciled_value: float = Field(default=0, ge=0)
    maximum_fee_variance: float = Field(default=0.1, ge=0, le=1)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    settlement_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_records(self) -> "SettlementCreate":
        position_ids = [item.position_id for item in self.positions]
        if len(position_ids) != len(set(position_ids)):
            raise ValueError("position_id values must be unique")
        settlement_ids = [item.settlement_id for item in self.settlements]
        if len(settlement_ids) != len(set(settlement_ids)):
            raise ValueError("settlement_id values must be unique")
        instruction_ids = [item.instruction_id for item in self.instructions]
        if len(instruction_ids) != len(set(instruction_ids)):
            raise ValueError("instruction_id values must be unique")
        known = set(position_ids)
        if any(item.position_id not in known for item in self.instructions):
            raise ValueError("instructions must reference known positions")
        return self


class SettlementActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|evaluate|propose-reconciliation|request-review|approve|start-settlement|record-settlement|start-reconciliation|record-cycle|confirm-reconciled|escalate|suspend|resume|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    instruction_ids: list[str] = Field(default_factory=list)
    settlement_id: str | None = Field(default=None, max_length=180)
    settlement_status: SettlementStatus | None = None
    actual_fee: float | None = Field(default=None, ge=0)
    cycle_healthy: bool | None = None
    unreconciled_value: float | None = Field(default=None, ge=0)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: SettlementState | None = None
    to_state: SettlementState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class SettlementGovernanceRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    treasury_record_id: str
    ledger_name: str
    positions: list[CustodyPosition]
    settlements: list[SettlementItem]
    instructions: list[ReconciliationInstruction]
    minimum_confidence: float
    maximum_unreconciled_value: float
    maximum_fee_variance: float
    required_healthy_cycles: int
    settlement_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: SettlementState = SettlementState.DRAFT
    selected_instruction_ids: list[str] = Field(default_factory=list)
    approval_actor: str | None = None
    unreconciled_value: float = 0
    consecutive_healthy_cycles: int = 0
    reconciliation_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
