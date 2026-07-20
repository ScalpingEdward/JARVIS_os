from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AdapterRegistryState(str, Enum):
    blocked = "blocked"
    unavailable = "unavailable"
    constrained = "constrained"
    eligible = "eligible"
    preferred = "preferred"


class AdapterCapability(BaseModel):
    supports_chart_vision: bool = True
    supports_ocr: bool = True
    supports_structured_json: bool = True
    supports_multiple_images: bool = False
    maximum_image_bytes: int = Field(default=12_000_000, gt=0)
    supported_mime_types: list[str] = Field(default_factory=lambda: ["image/jpeg", "image/png", "image/webp"])


class AdapterHealthObservation(BaseModel):
    available: bool = True
    success_rate_pct: float = Field(default=100, ge=0, le=100)
    p95_latency_ms: int = Field(default=0, ge=0)
    consecutive_failures: int = Field(default=0, ge=0)
    quota_remaining_pct: float = Field(default=100, ge=0, le=100)
    daily_cost_units: float = Field(default=0, ge=0)
    estimated_request_cost_units: float = Field(default=0, ge=0)
    credential_reference_configured: bool = False


class AdapterRegistryPolicy(BaseModel):
    minimum_success_rate_pct: float = Field(default=95, ge=0, le=100)
    maximum_p95_latency_ms: int = Field(default=20_000, gt=0)
    maximum_consecutive_failures: int = Field(default=2, ge=0)
    minimum_quota_remaining_pct: float = Field(default=10, ge=0, le=100)
    maximum_daily_cost_units: float = Field(default=100, gt=0)
    maximum_request_cost_units: float = Field(default=10, gt=0)
    require_credentials: bool = True
    require_chart_vision: bool = True
    require_structured_json: bool = True


class AdapterRegistryAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    provider_id: str = Field(min_length=1, max_length=100)
    adapter_id: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=60)
    capability: AdapterCapability = Field(default_factory=AdapterCapability)
    health: AdapterHealthObservation = Field(default_factory=AdapterHealthObservation)
    risk_brain_clear: bool = True
    human_preferred: bool = False
    policy: AdapterRegistryPolicy = Field(default_factory=AdapterRegistryPolicy)


class AdapterRegistryScores(BaseModel):
    capability_fit: int = Field(ge=0, le=100)
    reliability: int = Field(ge=0, le=100)
    latency_quality: int = Field(ge=0, le=100)
    quota_headroom: int = Field(ge=0, le=100)
    cost_efficiency: int = Field(ge=0, le=100)
    registry_confidence: int = Field(ge=0, le=100)


class AdapterRegistryAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    provider_id: str
    adapter_id: str
    version: str
    state: AdapterRegistryState
    routable: bool
    executable: bool
    recommended_action: str
    scores: AdapterRegistryScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AdapterRegistryStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: AdapterRegistryState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
