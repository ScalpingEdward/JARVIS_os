from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProbationState(str, Enum):
    blocked = "blocked"
    hold_canary = "hold-canary"
    extend_probation = "extend-probation"
    expand_controlled = "expand-controlled"
    graduate = "graduate"


class CanaryPerformance(BaseModel):
    live_trades: int = Field(ge=0)
    live_days: int = Field(ge=0)
    profit_factor: float = Field(ge=0)
    max_drawdown_share: float = Field(ge=0, le=1)
    slippage_bps: float = Field(ge=0)
    execution_error_rate: float = Field(ge=0, le=1)
    regime_coverage_score: int = Field(ge=0, le=100)
    operational_stability_score: int = Field(ge=0, le=100)
    incidents: int = Field(default=0, ge=0)


class ProbationPolicy(BaseModel):
    minimum_live_trades: int = Field(default=20, ge=1)
    minimum_live_days: int = Field(default=10, ge=1)
    minimum_profit_factor: float = Field(default=1.10, ge=0)
    maximum_drawdown_share: float = Field(default=0.05, gt=0, le=1)
    maximum_slippage_bps: float = Field(default=15, ge=0)
    maximum_execution_error_rate: float = Field(default=0.02, ge=0, le=1)
    minimum_regime_coverage_score: int = Field(default=60, ge=0, le=100)
    minimum_operational_stability_score: int = Field(default=75, ge=0, le=100)
    canary_capital_share: float = Field(default=0.10, gt=0, le=1)
    expansion_step_share: float = Field(default=0.15, gt=0, le=1)
    graduation_capital_share: float = Field(default=0.50, gt=0, le=1)


class ProbationAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    strategy_id: str = Field(min_length=1, max_length=100)
    succession_state: str = Field(min_length=1, max_length=40)
    approved_succession_capital: float = Field(gt=0)
    current_deployed_capital: float = Field(ge=0)
    human_approved: bool = False
    risk_brain_clear: bool = True
    performance: CanaryPerformance
    policy: ProbationPolicy = Field(default_factory=ProbationPolicy)


class ProbationScores(BaseModel):
    evidence_maturity: int = Field(ge=0, le=100)
    performance_quality: int = Field(ge=0, le=100)
    drawdown_safety: int = Field(ge=0, le=100)
    execution_quality: int = Field(ge=0, le=100)
    regime_coverage: int = Field(ge=0, le=100)
    operational_stability: int = Field(ge=0, le=100)
    graduation_confidence: int = Field(ge=0, le=100)


class ProbationAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    strategy_id: str
    state: ProbationState
    deployable: bool
    recommended_action: str
    approved_total_capital: float
    incremental_capital: float
    scores: ProbationScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProbationStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: ProbationState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
