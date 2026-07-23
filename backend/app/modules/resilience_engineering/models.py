from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ResilienceState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    DESIGNED = "designed"
    TEST_PLAN_READY = "test-plan-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class TestStatus(str, Enum):
    PLANNED = "planned"
    PASSED = "passed"
    DEGRADED = "degraded"
    FAILED = "failed"
    NOT_RUN = "not-run"


class ResilienceScenario(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=180)
    domain: str = Field(min_length=1, max_length=180)
    owner: str = Field(min_length=1, max_length=180)
    status: TestStatus = TestStatus.PLANNED
    target_recovery_minutes: int = Field(gt=0)
    observed_recovery_minutes: int | None = Field(default=None, ge=0)
    target_recovery_point_minutes: int = Field(ge=0)
    observed_recovery_point_minutes: int | None = Field(default=None, ge=0)
    service_availability: float = Field(default=1, ge=0, le=1)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResilienceControl(BaseModel):
    control_id: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=240)
    owner: str = Field(min_length=1, max_length=180)
    confidence: float = Field(ge=0, le=1)
    automated: bool = False
    reversible: bool = True
    evidence_refs: list[str] = Field(min_length=1)


class ResilienceCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    crisis_record_id: str = Field(min_length=1, max_length=180)
    program_name: str = Field(min_length=1, max_length=240)
    scenarios: list[ResilienceScenario] = Field(min_length=1)
    controls: list[ResilienceControl] = Field(min_length=1)
    minimum_control_confidence: float = Field(default=0.9, ge=0, le=1)
    maximum_failed_scenarios: int = Field(default=0, ge=0)
    maximum_degraded_scenarios: int = Field(default=0, ge=0)
    minimum_service_availability: float = Field(default=0.99, ge=0, le=1)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    resilience_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_records(self) -> "ResilienceCreate":
        scenario_ids = [item.scenario_id for item in self.scenarios]
        control_ids = [item.control_id for item in self.controls]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("scenario_id values must be unique")
        if len(control_ids) != len(set(control_ids)):
            raise ValueError("control_id values must be unique")
        return self


class ResilienceActionRequest(BaseModel):
    action: str = Field(pattern="^(prepare-evidence|design|prepare-test-plan|request-review|approve|execute|record-cycle|verify|escalate|suspend|resume|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    cycle_healthy: bool | None = None
    observed_failed_scenarios: int | None = Field(default=None, ge=0)
    observed_degraded_scenarios: int | None = Field(default=None, ge=0)
    observed_minimum_availability: float | None = Field(default=None, ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: ResilienceState | None = None
    to_state: ResilienceState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class ResilienceGovernanceRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    crisis_record_id: str
    program_name: str
    scenarios: list[ResilienceScenario]
    controls: list[ResilienceControl]
    minimum_control_confidence: float
    maximum_failed_scenarios: int
    maximum_degraded_scenarios: int
    minimum_service_availability: float
    required_healthy_cycles: int
    resilience_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: ResilienceState = ResilienceState.DRAFT
    failed_scenarios: int = 0
    degraded_scenarios: int = 0
    minimum_observed_availability: float = 1
    approval_actor: str | None = None
    consecutive_healthy_cycles: int = 0
    execution_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
