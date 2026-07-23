from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class PolicyEvolutionState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    EVALUATED = "evaluated"
    PROPOSED = "proposed"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    STAGED = "staged"
    CANARY = "canary"
    VALIDATING = "validating"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled-back"
    REJECTED = "rejected"
    FAILED = "failed"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class PolicyChangeType(str, Enum):
    THRESHOLD = "threshold"
    RETRY = "retry"
    ROUTING = "routing"
    STABILIZATION = "stabilization"
    OBSERVABILITY = "observability"
    REVIEW_GATE = "review-gate"


class PolicyChange(BaseModel):
    change_id: str = Field(min_length=1, max_length=160)
    change_type: PolicyChangeType
    policy_path: str = Field(min_length=1, max_length=300)
    baseline_value: float | int | str | bool | None = None
    proposed_value: float | int | str | bool
    confidence: float = Field(ge=0, le=1)
    expected_impact: str = Field(min_length=1, max_length=700)
    blast_radius: str = Field(min_length=1, max_length=300)
    rollback_condition: str = Field(min_length=1, max_length=700)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyEvolutionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    learning_record_id: str = Field(min_length=1, max_length=180)
    policy_domain: str = Field(min_length=1, max_length=240)
    changes: list[PolicyChange] = Field(min_length=1)
    minimum_confidence: float = Field(default=0.8, ge=0, le=1)
    canary_percentage: int = Field(default=10, ge=1, le=50)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    policy_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_changes(self) -> "PolicyEvolutionCreate":
        ids = [item.change_id for item in self.changes]
        if len(ids) != len(set(ids)):
            raise ValueError("change_id values must be unique")
        return self


class PolicyEvolutionActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|evaluate|propose|request-review|approve|stage|start-canary|record-validation|promote|rollback|reject|fail|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    change_ids: list[str] = Field(default_factory=list)
    validation_healthy: bool | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: PolicyEvolutionState | None = None
    to_state: PolicyEvolutionState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class PolicyEvolutionRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    learning_record_id: str
    policy_domain: str
    changes: list[PolicyChange]
    minimum_confidence: float
    canary_percentage: int
    required_healthy_cycles: int
    policy_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: PolicyEvolutionState = PolicyEvolutionState.DRAFT
    selected_change_ids: list[str] = Field(default_factory=list)
    approval_actor: str | None = None
    consecutive_healthy_cycles: int = 0
    validation_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
