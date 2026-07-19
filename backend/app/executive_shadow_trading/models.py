from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ShadowDirection(str, Enum):
    long = "long"
    short = "short"
    no_trade = "no_trade"


class ShadowOutcome(str, Enum):
    pending = "pending"
    win = "win"
    loss = "loss"
    breakeven = "breakeven"
    expired = "expired"
    invalidated = "invalidated"


class ExperimentStatus(str, Enum):
    draft = "draft"
    running = "running"
    paused = "paused"
    completed = "completed"
    rejected = "rejected"


class FactorSnapshot(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    value: float = Field(ge=-1_000_000, le=1_000_000)
    weight: float = Field(ge=0, le=1)
    available: bool = True
    rationale: str | None = Field(default=None, max_length=500)


class ShadowTradeCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    experiment_id: UUID
    strategy_id: str = Field(min_length=1, max_length=100)
    account_profile_id: str | None = Field(default=None, max_length=100)
    symbol: str = Field(min_length=1, max_length=30)
    session: str = Field(min_length=1, max_length=50)
    market_regime: str = Field(min_length=1, max_length=100)
    direction: ShadowDirection
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    target_price: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    factors: list[FactorSnapshot] = Field(default_factory=list, max_length=100)
    predicted_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_levels(self):
        if self.direction == ShadowDirection.long and not (self.stop_price < self.entry_price < self.target_price):
            raise ValueError("Long shadow trade requires stop < entry < target")
        if self.direction == ShadowDirection.short and not (self.target_price < self.entry_price < self.stop_price):
            raise ValueError("Short shadow trade requires target < entry < stop")
        return self


class ShadowTradeResult(BaseModel):
    outcome: ShadowOutcome
    exit_price: float | None = Field(default=None, gt=0)
    realized_r: float = Field(ge=-100, le=100)
    max_favorable_excursion_r: float = Field(ge=0, le=100)
    max_adverse_excursion_r: float = Field(ge=0, le=100)
    resolved_at: datetime = Field(default_factory=datetime.utcnow)
    notes: str | None = Field(default=None, max_length=1000)


class ShadowTrade(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    experiment_id: UUID
    strategy_id: str
    account_profile_id: str | None = None
    symbol: str
    session: str
    market_regime: str
    direction: ShadowDirection
    entry_price: float
    stop_price: float
    target_price: float
    confidence: float
    factors: list[FactorSnapshot]
    predicted_at: datetime
    expires_at: datetime | None = None
    outcome: ShadowOutcome = ShadowOutcome.pending
    result: ShadowTradeResult | None = None


class ExperimentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=150)
    strategy_id: str = Field(min_length=1, max_length=100)
    hypothesis: str = Field(min_length=1, max_length=1000)
    minimum_sample_size: int = Field(default=100, ge=20, le=100_000)
    baseline_experiment_id: UUID | None = None
    permitted_account_profiles: list[str] = Field(default_factory=list, max_length=100)


class StrategyExperiment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    strategy_id: str
    hypothesis: str
    minimum_sample_size: int
    baseline_experiment_id: UUID | None = None
    permitted_account_profiles: list[str]
    status: ExperimentStatus = ExperimentStatus.draft
    sample_size: int = 0
    win_rate: float = 0
    average_r: float = 0
    profit_factor: float | None = None
    expectancy_r: float = 0
    calibration_error: float = 0
    promotion_eligible: bool = False
    rejection_reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExperimentStatusUpdate(BaseModel):
    status: ExperimentStatus
    actor_id: str = Field(min_length=1, max_length=100)


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    entity_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    details: dict[str, object] = Field(default_factory=dict)


class ShadowTradingStatusResponse(BaseModel):
    module: str = "executive-shadow-trading"
    workspace_id: str
    experiments: int
    shadow_trades: int
    unresolved_trades: int
    autonomous_execution_enabled: bool = False


class ExperimentListResponse(BaseModel):
    items: list[StrategyExperiment]
    count: int


class ShadowTradeListResponse(BaseModel):
    items: list[ShadowTrade]
    count: int
