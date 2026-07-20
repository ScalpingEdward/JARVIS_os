from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AdapterExecutionState(str, Enum):
    blocked = "blocked"
    credential_required = "credential-required"
    retry_scheduled = "retry-scheduled"
    failed = "failed"
    completed = "completed"
    dispatched = "dispatched"


class AdapterAttempt(BaseModel):
    attempt_number: int = Field(ge=1, le=10)
    success: bool = False
    timed_out: bool = False
    retryable: bool = False
    latency_ms: int = Field(default=0, ge=0)
    response_bytes: int = Field(default=0, ge=0)
    estimated_cost_units: float = Field(default=0, ge=0)
    http_status: int | None = Field(default=None, ge=100, le=599)
    schema_valid: bool = False
    safety_clear: bool = True
    extraction_confidence: int = Field(default=0, ge=0, le=100)
    error_code: str | None = Field(default=None, max_length=100)


class AdapterExecutionPolicy(BaseModel):
    maximum_attempts: int = Field(default=3, ge=1, le=10)
    maximum_latency_ms: int = Field(default=20_000, gt=0)
    maximum_response_bytes: int = Field(default=5_000_000, gt=0)
    maximum_cost_units: float = Field(default=10, gt=0)
    minimum_extraction_confidence: int = Field(default=80, ge=0, le=100)
    require_schema_valid: bool = True
    require_safety_clear: bool = True
    require_isolated_credential_reference: bool = True


class AdapterExecutionAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    routing_assessment_id: str = Field(min_length=1, max_length=120)
    routing_state: str = Field(min_length=1, max_length=40)
    provider_id: str = Field(min_length=1, max_length=100)
    adapter_id: str = Field(min_length=1, max_length=100)
    image_sha256: str = Field(min_length=32, max_length=64)
    credential_reference: str | None = Field(default=None, max_length=250)
    credential_resolved: bool = False
    request_payload_redacted: bool = True
    risk_brain_clear: bool = True
    attempts: list[AdapterAttempt] = Field(min_length=1, max_length=10)
    policy: AdapterExecutionPolicy = Field(default_factory=AdapterExecutionPolicy)


class AdapterExecutionScores(BaseModel):
    credential_isolation: int = Field(ge=0, le=100)
    reliability: int = Field(ge=0, le=100)
    latency_quality: int = Field(ge=0, le=100)
    cost_efficiency: int = Field(ge=0, le=100)
    result_quality: int = Field(ge=0, le=100)
    execution_confidence: int = Field(ge=0, le=100)


class AdapterExecutionAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    routing_assessment_id: str
    provider_id: str
    adapter_id: str
    image_sha256: str
    state: AdapterExecutionState
    selected_attempt_number: int | None
    dispatchable: bool
    target_module: str | None
    recommended_action: str
    scores: AdapterExecutionScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AdapterExecutionStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: AdapterExecutionState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
