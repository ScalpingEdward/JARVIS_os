from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PromotionState(str, Enum):
    hold = "hold"
    eligible = "eligible"
    promote_risk = "promote_risk"
    expand_symbols = "expand_symbols"
    expand_accounts = "expand_accounts"
    blocked = "blocked"


class ScalingDimension(str, Enum):
    risk = "risk"
    capital = "capital"
    symbols = "symbols"
    accounts = "accounts"


class ScalingGate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    passed: bool
    mandatory: bool = True
    detail: str = Field(default="", max_length=300)


class PromotionInput(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    strategy_id: str = Field(min_length=1, max_length=100)
    current_risk_multiplier: float = Field(default=0.25, ge=0, le=1)
    requested_risk_multiplier: float = Field(default=0.5, ge=0, le=1)
    current_capital: float = Field(default=0, ge=0)
    requested_capital: float = Field(default=0, ge=0)
    current_symbol_count: int = Field(default=1, ge=1, le=100)
    requested_symbol_count: int = Field(default=1, ge=1, le=100)
    current_account_count: int = Field(default=1, ge=1, le=100)
    requested_account_count: int = Field(default=1, ge=1, le=100)
    monitoring_state: str = Field(default="stable", max_length=30)
    promotion_eligible: bool = False
    overall_health: float = Field(default=75, ge=0, le=100)
    risk_stability: float = Field(default=75, ge=0, le=100)
    execution_stability: float = Field(default=75, ge=0, le=100)
    operational_stability: float = Field(default=75, ge=0, le=100)
    evidence_quality: float = Field(default=75, ge=0, le=100)
    sample_trades: int = Field(default=0, ge=0)
    minimum_sample_trades: int = Field(default=30, ge=1)
    stable_hours: int = Field(default=0, ge=0)
    minimum_stable_hours: int = Field(default=24, ge=1)
    max_drawdown_percent: float = Field(default=0, ge=0, le=100)
    drawdown_limit_percent: float = Field(default=5, gt=0, le=100)
    open_critical_issues: int = Field(default=0, ge=0)
    human_approval: bool = False
    gates: list[ScalingGate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_requests(self):
        if self.requested_risk_multiplier < self.current_risk_multiplier:
            raise ValueError("Requested risk multiplier cannot be below current multiplier")
        if self.requested_symbol_count < self.current_symbol_count:
            raise ValueError("Requested symbol count cannot be below current count")
        if self.requested_account_count < self.current_account_count:
            raise ValueError("Requested account count cannot be below current count")
        names = [gate.name for gate in self.gates]
        if len(names) != len(set(names)):
            raise ValueError("Scaling gate names must be unique")
        return self


class PromotionScores(BaseModel):
    readiness: float = Field(ge=0, le=100)
    risk_capacity: float = Field(ge=0, le=100)
    execution_capacity: float = Field(ge=0, le=100)
    operational_capacity: float = Field(ge=0, le=100)
    evidence_strength: float = Field(ge=0, le=100)
    scaling_confidence: float = Field(ge=0, le=100)


class ScalingStep(BaseModel):
    order: int = Field(ge=1)
    dimension: ScalingDimension
    target: str
    verification: str


class PromotionAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    source_key: str
    strategy_id: str
    state: PromotionState
    scores: PromotionScores
    approved_risk_multiplier: float = Field(ge=0, le=1)
    approved_capital: float = Field(ge=0)
    approved_symbol_count: int = Field(ge=1)
    approved_account_count: int = Field(ge=1)
    scaling_plan: list[ScalingStep]
    blockers: list[str]
    reasons: list[str]
    human_approval_required: bool = True
    autonomous_scaling_enabled: bool = False
    assessed_at: datetime


class PromotionStatusResponse(BaseModel):
    version: str = "18.41"
    assessments: int
    eligible: int
    promoted: int
    held: int
    blocked: int
    autonomous_scaling_enabled: bool = False


class PromotionListResponse(BaseModel):
    items: list[PromotionAssessment]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    assessment_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
