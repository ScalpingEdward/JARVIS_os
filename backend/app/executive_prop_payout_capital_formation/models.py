from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PayoutStatus(StrEnum):
    EXPECTED = "expected"
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    RECEIVED = "received"
    REJECTED = "rejected"


class FormationState(StrEnum):
    HOLD = "hold"
    PLAN = "plan"
    APPROVED = "approved"
    BLOCKED = "blocked"


class UseCategory(StrEnum):
    TAX_RESERVE = "tax_reserve"
    EMERGENCY_RESERVE = "emergency_reserve"
    LIVING_COSTS = "living_costs"
    LIVE_TRADING_CAPITAL = "live_trading_capital"
    PROP_GROWTH = "prop_growth"
    LONG_TERM_INVESTING = "long_term_investing"
    FREE_LIQUIDITY = "free_liquidity"


class PropPayout(BaseModel):
    prop_firm: str = Field(min_length=1, max_length=100)
    account_label: str = Field(min_length=1, max_length=100)
    payout_amount: float = Field(ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    status: PayoutStatus
    account_nominal_size: float = Field(default=0, ge=0)


class CapitalPolicy(BaseModel):
    tax_reserve_pct: float = Field(default=25, ge=0, le=100)
    emergency_reserve_pct: float = Field(default=10, ge=0, le=100)
    living_costs_pct: float = Field(default=20, ge=0, le=100)
    live_trading_capital_pct: float = Field(default=30, ge=0, le=100)
    prop_growth_pct: float = Field(default=10, ge=0, le=100)
    long_term_investing_pct: float = Field(default=5, ge=0, le=100)

    @model_validator(mode="after")
    def validate_total(self):
        total = sum((self.tax_reserve_pct, self.emergency_reserve_pct, self.living_costs_pct,
                     self.live_trading_capital_pct, self.prop_growth_pct, self.long_term_investing_pct))
        if total > 100:
            raise ValueError("Capital policy percentages must not exceed 100")
        return self


class FormationAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=150)
    actor_id: str = Field(min_length=1, max_length=100)
    payouts: list[PropPayout] = Field(min_length=1)
    policy: CapitalPolicy = Field(default_factory=CapitalPolicy)
    human_approval: bool = False
    minimum_received_amount: float = Field(default=1, ge=0)


class AllocationLine(BaseModel):
    category: UseCategory
    amount: float
    percentage: float
    deployable: bool
    reason: str


class FormationAssessment(BaseModel):
    assessment_id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: FormationState
    received_cash: float
    expected_cash: float
    prop_nominal_capital: float
    allocations: list[AllocationLine]
    live_capital_contribution: float
    prop_growth_budget: float
    protected_reserves: float
    free_liquidity: float
    reasons: list[str]
    advisory_only: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AssessmentListResponse(BaseModel):
    items: list[FormationAssessment]
    count: int


class StatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: FormationState | None = None


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
