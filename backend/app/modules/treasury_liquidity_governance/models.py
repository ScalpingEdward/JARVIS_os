from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class TreasuryState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    EVALUATED = "evaluated"
    FUNDING_PROPOSED = "funding-proposed"
    EXECUTIVE_REVIEW_REQUIRED = "executive-review-required"
    APPROVED = "approved"
    FUNDED = "funded"
    MONITORING = "monitoring"
    LIQUID = "liquid"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class FundingAction(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    TRANSFER = "transfer"
    RESERVE = "reserve"
    RELEASE = "release"
    HOLD = "hold"


class TreasuryAccount(BaseModel):
    account_id: str = Field(min_length=1, max_length=180)
    provider_id: str = Field(min_length=1, max_length=180)
    currency: str = Field(min_length=1, max_length=20)
    available_balance: float = Field(ge=0)
    reserved_balance: float = Field(default=0, ge=0)
    minimum_operating_balance: float = Field(default=0, ge=0)
    maximum_exposure: float = Field(gt=0)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FundingInstruction(BaseModel):
    instruction_id: str = Field(min_length=1, max_length=160)
    action: FundingAction
    source_account_id: str | None = Field(default=None, max_length=180)
    target_account_id: str | None = Field(default=None, max_length=180)
    amount: float = Field(gt=0)
    currency: str = Field(min_length=1, max_length=20)
    rationale: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(min_length=1)


class TreasuryCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    portfolio_record_id: str = Field(min_length=1, max_length=180)
    treasury_name: str = Field(min_length=1, max_length=240)
    accounts: list[TreasuryAccount] = Field(min_length=1)
    instructions: list[FundingInstruction] = Field(default_factory=list)
    minimum_confidence: float = Field(default=0.8, ge=0, le=1)
    minimum_liquidity_ratio: float = Field(default=0.2, gt=0, le=1)
    maximum_total_exposure: float = Field(gt=0)
    maximum_single_provider_weight: float = Field(default=0.5, gt=0, le=1)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    treasury_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_treasury(self) -> "TreasuryCreate":
        account_ids = [item.account_id for item in self.accounts]
        if len(account_ids) != len(set(account_ids)):
            raise ValueError("account_id values must be unique")
        instruction_ids = [item.instruction_id for item in self.instructions]
        if len(instruction_ids) != len(set(instruction_ids)):
            raise ValueError("instruction_id values must be unique")
        known = set(account_ids)
        for item in self.instructions:
            if item.source_account_id and item.source_account_id not in known:
                raise ValueError("source_account_id must reference a known account")
            if item.target_account_id and item.target_account_id not in known:
                raise ValueError("target_account_id must reference a known account")
            if item.action == FundingAction.TRANSFER and (not item.source_account_id or not item.target_account_id):
                raise ValueError("transfer instructions require source and target accounts")
        return self


class TreasuryActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|evaluate|propose-funding|request-review|approve|execute-funding|record-cycle|confirm-liquid|escalate|suspend|resume|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    instruction_ids: list[str] = Field(default_factory=list)
    cycle_healthy: bool | None = None
    liquidity_ratio: float | None = Field(default=None, ge=0, le=1)
    total_exposure: float | None = Field(default=None, ge=0)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: TreasuryState | None = None
    to_state: TreasuryState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class TreasuryGovernanceRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    portfolio_record_id: str
    treasury_name: str
    accounts: list[TreasuryAccount]
    instructions: list[FundingInstruction]
    minimum_confidence: float
    minimum_liquidity_ratio: float
    maximum_total_exposure: float
    maximum_single_provider_weight: float
    required_healthy_cycles: int
    treasury_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: TreasuryState = TreasuryState.DRAFT
    selected_instruction_ids: list[str] = Field(default_factory=list)
    approval_actor: str | None = None
    liquidity_ratio: float = 1
    total_exposure: float = 0
    consecutive_healthy_cycles: int = 0
    funding_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
