from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class TreasuryState(str, Enum):
    blocked = "blocked"
    preserve = "preserve"
    balanced = "balanced"
    growth_ready = "growth-ready"
    withdrawal_review = "withdrawal-review"


class WealthBucket(str, Enum):
    tax_reserve = "tax-reserve"
    emergency_reserve = "emergency-reserve"
    living_costs = "living-costs"
    live_trading = "live-trading"
    long_term_investing = "long-term-investing"
    opportunity_cash = "opportunity-cash"


class TreasuryPolicy(BaseModel):
    minimum_tax_reserve: float = Field(ge=0)
    minimum_emergency_reserve: float = Field(ge=0)
    monthly_living_costs: float = Field(ge=0)
    minimum_runway_months: int = Field(default=6, ge=1, le=36)
    max_live_trading_share: float = Field(default=0.35, ge=0, le=1)
    max_investment_share: float = Field(default=0.35, ge=0, le=1)
    max_single_withdrawal_share: float = Field(default=0.10, ge=0, le=1)


class TreasuryAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    owned_cash: float = Field(ge=0)
    received_prop_payout_cash: float = Field(default=0, ge=0)
    existing_tax_reserve: float = Field(default=0, ge=0)
    existing_emergency_reserve: float = Field(default=0, ge=0)
    existing_live_trading_capital: float = Field(default=0, ge=0)
    existing_long_term_investments: float = Field(default=0, ge=0)
    requested_withdrawal: float = Field(default=0, ge=0)
    human_approved: bool = False
    prop_nominal_capital: float = Field(default=0, ge=0, description="Recorded only for exclusion; never treated as owned wealth.")
    policy: TreasuryPolicy

    @model_validator(mode="after")
    def validate_owned_capital(self):
        if self.requested_withdrawal > self.owned_cash + self.received_prop_payout_cash:
            raise ValueError("Requested withdrawal exceeds owned liquid capital")
        return self


class TreasuryAllocationLine(BaseModel):
    bucket: WealthBucket
    current_amount: float
    target_amount: float
    recommended_change: float
    deployable: bool
    rationale: str


class TreasuryScores(BaseModel):
    liquidity_health: int = Field(ge=0, le=100)
    reserve_adequacy: int = Field(ge=0, le=100)
    investment_capacity: int = Field(ge=0, le=100)
    withdrawal_sustainability: int = Field(ge=0, le=100)
    treasury_stability: int = Field(ge=0, le=100)
    wealth_formation_confidence: int = Field(ge=0, le=100)


class TreasuryAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    state: TreasuryState
    owned_capital: float
    excluded_prop_nominal_capital: float
    protected_capital: float
    growth_capital: float
    approved_withdrawal: float
    allocation_lines: list[TreasuryAllocationLine]
    scores: TreasuryScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TreasuryStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: TreasuryState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
