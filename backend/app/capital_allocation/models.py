from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AllocationTargetType(str, Enum):
    account = "account"
    strategy = "strategy"
    market = "market"


class AllocationMode(str, Enum):
    defensive = "defensive"
    balanced = "balanced"
    growth = "growth"


class AllocationTarget(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=2, max_length=120)
    target_type: AllocationTargetType
    current_weight: float = Field(ge=0, le=1)
    expected_return: float = Field(default=0.0, ge=-1, le=5)
    volatility: float = Field(default=0.2, ge=0, le=5)
    drawdown: float = Field(default=0.0, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    min_weight: float = Field(default=0.0, ge=0, le=1)
    max_weight: float = Field(default=1.0, ge=0, le=1)
    enabled: bool = True


class AllocationRequest(BaseModel):
    capital: float = Field(gt=0)
    mode: AllocationMode = AllocationMode.balanced
    max_total_risk: float = Field(default=0.02, gt=0, le=0.2)
    reserve_weight: float = Field(default=0.15, ge=0, lt=1)
    targets: list[AllocationTarget] = Field(min_length=1, max_length=100)


class AllocationLine(BaseModel):
    target_id: UUID
    name: str
    target_type: AllocationTargetType
    current_weight: float
    recommended_weight: float
    allocated_capital: float
    risk_budget: float
    action: str
    reasons: list[str]


class AllocationPlan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    owner_name: str = "MASTER Brano"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mode: AllocationMode
    total_capital: float
    reserve_capital: float
    investable_capital: float
    lines: list[AllocationLine]
    warnings: list[str]
    executive_recommendation: str
    requires_human_approval: bool = True
    automatic_execution: bool = False
    automatic_order_execution: bool = False


class RebalanceRequest(BaseModel):
    plan_id: UUID
    drift_threshold: float = Field(default=0.05, gt=0, le=0.5)


class RebalanceItem(BaseModel):
    target_id: UUID
    name: str
    current_weight: float
    target_weight: float
    drift: float
    recommendation: str


class RebalanceReport(BaseModel):
    plan_id: UUID
    items: list[RebalanceItem]
    requires_human_approval: bool = True
    automatic_execution: bool = False


class AllocationStatus(BaseModel):
    service: str = "capital-allocation"
    owner_name: str = "MASTER Brano"
    plans: int
    advisory_only: bool = True
    automatic_execution: bool = False
    automatic_order_execution: bool = False
