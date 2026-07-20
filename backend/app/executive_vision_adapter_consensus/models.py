from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ConsensusState(str, Enum):
    blocked = "blocked"
    retry_required = "retry-required"
    disagreement = "disagreement"
    normalized = "normalized"
    dispatched = "dispatched"


class AdapterExtraction(BaseModel):
    provider_id: str = Field(min_length=1, max_length=100)
    invocation_id: str = Field(min_length=1, max_length=160)
    success: bool = True
    schema_valid: bool = True
    safety_clear: bool = True
    confidence: int = Field(default=0, ge=0, le=100)
    symbol: str | None = Field(default=None, max_length=40)
    timeframe: str | None = Field(default=None, max_length=20)
    direction: str = Field(default="unknown", pattern="^(long|short|unknown)$")
    entry_price: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profits: list[float] = Field(default_factory=list, max_length=10)
    ict_features: list[str] = Field(default_factory=list, max_length=30)
    latency_ms: int = Field(default=0, ge=0)
    error: str | None = Field(default=None, max_length=500)


class ConsensusPolicy(BaseModel):
    minimum_adapter_confidence: int = Field(default=80, ge=0, le=100)
    minimum_agreeing_adapters: int = Field(default=2, ge=1, le=10)
    maximum_entry_deviation_bps: float = Field(default=25, ge=0)
    require_symbol: bool = True
    require_timeframe: bool = True
    require_trade_levels: bool = True
    require_consensus_for_multiple_results: bool = True
    allow_single_adapter_with_human_approval: bool = True


class ConsensusAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    routing_assessment_id: str = Field(min_length=1, max_length=120)
    routing_state: str = Field(min_length=1, max_length=40)
    image_sha256: str = Field(min_length=32, max_length=64)
    risk_brain_clear: bool = True
    human_approved: bool = False
    extractions: list[AdapterExtraction] = Field(min_length=1, max_length=10)
    policy: ConsensusPolicy = Field(default_factory=ConsensusPolicy)


class NormalizedExtraction(BaseModel):
    symbol: str | None
    timeframe: str | None
    direction: str
    entry_price: float | None
    stop_loss: float | None
    take_profits: list[float]
    ict_features: list[str]
    agreeing_provider_ids: list[str]


class ConsensusScores(BaseModel):
    adapter_success: int = Field(ge=0, le=100)
    schema_quality: int = Field(ge=0, le=100)
    directional_agreement: int = Field(ge=0, le=100)
    level_agreement: int = Field(ge=0, le=100)
    normalization_confidence: int = Field(ge=0, le=100)


class ConsensusAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    routing_assessment_id: str
    image_sha256: str
    state: ConsensusState
    dispatchable: bool
    target_module: str | None
    recommended_action: str
    normalized_extraction: NormalizedExtraction | None
    scores: ConsensusScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConsensusStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: ConsensusState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
