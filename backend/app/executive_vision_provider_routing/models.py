from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class VisionRoutingState(str, Enum):
    blocked = "blocked"
    queued = "queued"
    fallback_required = "fallback-required"
    extracted = "extracted"
    dispatched = "dispatched"


class ProviderObservation(BaseModel):
    provider_id: str = Field(min_length=1, max_length=100)
    available: bool = True
    latency_ms: int = Field(default=0, ge=0)
    estimated_cost_units: float = Field(default=0, ge=0)
    extraction_confidence: int = Field(default=0, ge=0, le=100)
    schema_valid: bool = False
    safety_clear: bool = True
    timed_out: bool = False
    error_count: int = Field(default=0, ge=0)


class VisionRoutingPolicy(BaseModel):
    preferred_provider_id: str = Field(default="primary", min_length=1, max_length=100)
    minimum_extraction_confidence: int = Field(default=80, ge=0, le=100)
    maximum_latency_ms: int = Field(default=20_000, gt=0)
    maximum_cost_units: float = Field(default=10, gt=0)
    maximum_provider_errors: int = Field(default=2, ge=0)
    allow_fallback: bool = True
    require_schema_valid: bool = True
    require_human_approval_for_fallback: bool = False


class VisionRoutingAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    ingestion_id: str = Field(min_length=1, max_length=120)
    image_sha256: str = Field(min_length=32, max_length=64)
    target_module: str = Field(default="executive-telegram-chart-vision-signal-intelligence", min_length=1, max_length=160)
    risk_brain_clear: bool = True
    human_approved: bool = False
    providers: list[ProviderObservation] = Field(min_length=1, max_length=10)
    policy: VisionRoutingPolicy = Field(default_factory=VisionRoutingPolicy)


class VisionRoutingScores(BaseModel):
    availability: int = Field(ge=0, le=100)
    extraction_quality: int = Field(ge=0, le=100)
    latency_quality: int = Field(ge=0, le=100)
    cost_efficiency: int = Field(ge=0, le=100)
    dispatch_confidence: int = Field(ge=0, le=100)


class VisionRoutingAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    ingestion_id: str
    image_sha256: str
    state: VisionRoutingState
    selected_provider_id: str | None
    fallback_used: bool
    dispatchable: bool
    target_module: str | None
    recommended_action: str
    scores: VisionRoutingScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VisionRoutingStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: VisionRoutingState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
