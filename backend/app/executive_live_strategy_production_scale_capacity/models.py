from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProductionScaleState(str, Enum):
    blocked = "blocked"
    hold_capacity = "hold-capacity"
    reduce_exposure = "reduce-exposure"
    scale_controlled = "scale-controlled"
    production_ready = "production-ready"


class ProductionPerformance(BaseModel):
    live_trades: int = Field(ge=0)
    live_days: int = Field(ge=0)
    profit_factor: float = Field(ge=0)
    max_drawdown_share: float = Field(ge=0, le=1)
    capacity_utilization_share: float = Field(ge=0, le=1)
    slippage_bps: float = Field(ge=0)
    fill_quality_score: int = Field(ge=0, le=100)
    regime_coverage_score: int = Field(ge=0, le=100)
    operational_stability_score: int = Field(ge=0, le=100)
    concentration_share: float = Field(ge=0, le=1)
    active_incidents: int = Field(default=0, ge=0)


class ProductionScalePolicy(BaseModel):
    minimum_live_trades: int = Field(default=60, ge=1)
    minimum_live_days: int = Field(default=30, ge=1)
    minimum_profit_factor: float = Field(default=1.15, ge=0)
    maximum_drawdown_share: float = Field(default=0.08, gt=0, le=1)
    maximum_capacity_utilization_share: float = Field(default=0.80, gt=0, le=1)
    maximum_slippage_bps: float = Field(default=20, ge=0)
    minimum_fill_quality_score: int = Field(default=75, ge=0, le=100)
    minimum_regime_coverage_score: int = Field(default=70, ge=0, le=100)
    minimum_operational_stability_score: int = Field(default=80, ge=0, le=100)
    maximum_concentration_share: float = Field(default=0.35, gt=0, le=1)
    scale_step_share: float = Field(default=0.15, gt=0, le=1)
    maximum_production_capital_share: float = Field(default=0.85, gt=0, le=1)


class ProductionScaleAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    strategy_id: str = Field(min_length=1, max_length=100)
    probation_state: str = Field(min_length=1, max_length=40)
    approved_strategy_capital: float = Field(gt=0)
    current_deployed_capital: float = Field(ge=0)
    human_approved: bool = False
    risk_brain_clear: bool = True
    performance: ProductionPerformance
    policy: ProductionScalePolicy = Field(default_factory=ProductionScalePolicy)


class ProductionScaleScores(BaseModel):
    evidence_maturity: int = Field(ge=0, le=100)
    performance_quality: int = Field(ge=0, le=100)
    drawdown_safety: int = Field(ge=0, le=100)
    capacity_headroom: int = Field(ge=0, le=100)
    execution_quality: int = Field(ge=0, le=100)
    diversification_safety: int = Field(ge=0, le=100)
    production_confidence: int = Field(ge=0, le=100)


class ProductionScaleAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    strategy_id: str
    state: ProductionScaleState
    deployable: bool
    recommended_action: str
    approved_total_capital: float
    incremental_capital: float
    scores: ProductionScaleScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductionScaleStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: ProductionScaleState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
