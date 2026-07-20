from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SuccessionState(str, Enum):
    blocked = "blocked"
    preserve_capital = "preserve-capital"
    observe_candidate = "observe-candidate"
    validate_candidate = "validate-candidate"
    succession_ready = "succession-ready"


class ReplacementCandidate(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=100)
    evidence_trades: int = Field(ge=0)
    profit_factor: float = Field(ge=0)
    max_drawdown_share: float = Field(ge=0, le=1)
    regime_fit_score: int = Field(ge=0, le=100)
    execution_quality_score: int = Field(ge=0, le=100)
    correlation_to_retired_strategy: float = Field(ge=-1, le=1)
    operational_readiness_score: int = Field(ge=0, le=100)


class SuccessionPolicy(BaseModel):
    minimum_evidence_trades: int = Field(default=30, ge=1)
    minimum_profit_factor: float = Field(default=1.15, ge=0)
    maximum_drawdown_share: float = Field(default=0.10, gt=0, le=1)
    minimum_regime_fit_score: int = Field(default=65, ge=0, le=100)
    minimum_execution_quality_score: int = Field(default=70, ge=0, le=100)
    minimum_operational_readiness_score: int = Field(default=75, ge=0, le=100)
    maximum_absolute_correlation: float = Field(default=0.80, ge=0, le=1)
    maximum_replacement_capital_share: float = Field(default=0.25, gt=0, le=1)


class SuccessionAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    retired_strategy_id: str = Field(min_length=1, max_length=100)
    retirement_state: str = Field(min_length=1, max_length=40)
    released_capital: float = Field(gt=0)
    human_approved: bool = False
    risk_brain_clear: bool = True
    archive_complete: bool = False
    candidate: ReplacementCandidate | None = None
    policy: SuccessionPolicy = Field(default_factory=SuccessionPolicy)


class SuccessionScores(BaseModel):
    evidence_strength: int = Field(ge=0, le=100)
    performance_quality: int = Field(ge=0, le=100)
    drawdown_safety: int = Field(ge=0, le=100)
    diversification_value: int = Field(ge=0, le=100)
    operational_readiness: int = Field(ge=0, le=100)
    succession_confidence: int = Field(ge=0, le=100)


class SuccessionAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    retired_strategy_id: str
    candidate_strategy_id: str | None
    state: SuccessionState
    deployable: bool
    recommended_action: str
    approved_capital: float
    scores: SuccessionScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SuccessionStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: SuccessionState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
