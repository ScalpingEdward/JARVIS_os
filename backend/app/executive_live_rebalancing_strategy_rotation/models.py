from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RebalancingState(str, Enum):
    blocked = "blocked"
    hold = "hold"
    monitor = "monitor"
    rebalance = "rebalance"
    rotation_ready = "rotation-ready"


class RotationAction(str, Enum):
    hold = "hold"
    reduce = "reduce"
    pause = "pause"
    increase = "increase"
    rotate = "rotate"


class StrategyPosition(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=100)
    broker_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=30)
    current_capital: float = Field(ge=0)
    target_capital: float = Field(ge=0)
    current_risk_share: float = Field(ge=0, le=1)
    performance_score: int = Field(ge=0, le=100)
    stability_score: int = Field(ge=0, le=100)
    drawdown_share: float = Field(default=0, ge=0, le=1)
    correlation_group: str = Field(default="independent", min_length=1, max_length=100)
    enabled: bool = True


class RotationPolicy(BaseModel):
    max_strategy_risk_share: float = Field(default=0.35, gt=0, le=1)
    max_strategy_drawdown_share: float = Field(default=0.10, gt=0, le=1)
    minimum_performance_score: int = Field(default=55, ge=0, le=100)
    minimum_stability_score: int = Field(default=60, ge=0, le=100)
    minimum_rotation_amount: float = Field(default=100, ge=0)
    max_rotation_share_per_cycle: float = Field(default=0.25, gt=0, le=1)


class RebalancingAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    owned_live_capital: float = Field(ge=0)
    human_approved: bool = False
    risk_brain_clear: bool = True
    portfolio_drawdown_share: float = Field(default=0, ge=0, le=1)
    positions: list[StrategyPosition] = Field(min_length=1)
    policy: RotationPolicy


class RotationLine(BaseModel):
    strategy_id: str
    broker_id: str
    symbol: str
    current_capital: float
    recommended_capital: float
    recommended_change: float
    action: RotationAction
    deployable: bool
    reasons: list[str]


class RebalancingScores(BaseModel):
    strategy_quality: int = Field(ge=0, le=100)
    drawdown_safety: int = Field(ge=0, le=100)
    rotation_efficiency: int = Field(ge=0, le=100)
    capital_alignment: int = Field(ge=0, le=100)
    rebalancing_confidence: int = Field(ge=0, le=100)


class RebalancingAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    state: RebalancingState
    owned_live_capital: float
    planned_rotation_capital: float
    approved_rotation_capital: float
    rotation_lines: list[RotationLine]
    scores: RebalancingScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RebalancingStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: RebalancingState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
