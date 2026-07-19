from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AllocationState(str, Enum):
    blocked = "blocked"
    hold = "hold"
    rebalance = "rebalance"
    deploy_reduced = "deploy_reduced"
    deploy_full = "deploy_full"


class AllocationCandidate(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=100)
    account_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=30)
    requested_capital: float = Field(gt=0)
    requested_risk_pct: float = Field(gt=0, le=10)
    confidence_score: float = Field(ge=0, le=100)
    stability_score: float = Field(ge=0, le=100)
    correlation_score: float = Field(ge=0, le=100)
    current_account_exposure_pct: float = Field(ge=0, le=100)
    current_symbol_exposure_pct: float = Field(ge=0, le=100)


class AllocationInput(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    approved_total_capital: float = Field(gt=0)
    reserve_capital_pct: float = Field(default=20, ge=0, le=100)
    max_account_exposure_pct: float = Field(default=35, gt=0, le=100)
    max_symbol_exposure_pct: float = Field(default=25, gt=0, le=100)
    max_strategy_exposure_pct: float = Field(default=30, gt=0, le=100)
    max_correlation_score: float = Field(default=75, ge=0, le=100)
    risk_brain_state: str = Field(default="normal", max_length=30)
    promotion_state: str = Field(default="eligible", max_length=40)
    human_approval: bool = False
    candidates: list[AllocationCandidate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_candidates(self):
        keys = [(item.strategy_id, item.account_id, item.symbol) for item in self.candidates]
        if len(keys) != len(set(keys)):
            raise ValueError("Allocation candidates must be unique")
        return self


class DeploymentLine(BaseModel):
    strategy_id: str
    account_id: str
    symbol: str
    approved_capital: float = Field(ge=0)
    approved_risk_pct: float = Field(ge=0, le=10)
    allocation_weight_pct: float = Field(ge=0, le=100)
    action: str
    reasons: list[str]


class AllocationScores(BaseModel):
    capital_efficiency: float = Field(ge=0, le=100)
    diversification: float = Field(ge=0, le=100)
    concentration_safety: float = Field(ge=0, le=100)
    risk_alignment: float = Field(ge=0, le=100)
    deployment_confidence: float = Field(ge=0, le=100)


class AllocationAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    source_key: str
    state: AllocationState
    scores: AllocationScores
    deployment_plan: list[DeploymentLine]
    allocated_capital: float
    reserve_capital: float
    unallocated_capital: float
    reasons: list[str]
    human_approval_required: bool = True
    autonomous_deployment_enabled: bool = False
    assessed_at: datetime


class AllocationStatusResponse(BaseModel):
    version: str = "18.42"
    assessments: int
    blocked: int
    held: int
    rebalances: int
    reduced_deployments: int
    full_deployments: int
    autonomous_deployment_enabled: bool = False


class AllocationListResponse(BaseModel):
    items: list[AllocationAssessment]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    assessment_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
