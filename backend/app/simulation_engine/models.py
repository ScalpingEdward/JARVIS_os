from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class SimulationKind(str, Enum):
    trading = "trading"
    business = "business"
    operations = "operations"
    decision = "decision"
    what_if = "what_if"
    monte_carlo = "monte_carlo"


class SimulationState(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ScenarioInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    probability: float = Field(default=1.0, ge=0, le=1)
    impact: float = Field(default=0, ge=-100, le=100)
    cost: float = Field(default=0, ge=0)
    duration_hours: float = Field(default=0, ge=0)
    risk: float = Field(default=0, ge=0, le=100)
    metadata: dict[str, float | int | str | bool] = Field(default_factory=dict)


class TradingSimulationInput(BaseModel):
    instrument: str = Field(min_length=1, max_length=40)
    entry: float
    stop_loss: float
    take_profit: float
    risk_percent: float = Field(gt=0, le=10)
    starting_balance: float = Field(gt=0)
    win_probability: float = Field(default=0.5, ge=0, le=1)
    trades: int = Field(default=100, ge=1, le=100000)

    @model_validator(mode="after")
    def validate_prices(self):
        if self.entry == self.stop_loss:
            raise ValueError("Entry and stop loss must differ")
        return self


class SimulationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: SimulationKind
    scenarios: list[ScenarioInput] = Field(default_factory=list, max_length=50)
    trading: TradingSimulationInput | None = None
    iterations: int = Field(default=1000, ge=1, le=100000)
    seed: int | None = None
    created_by: str = Field(default="human", min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_payload(self):
        if self.kind in {SimulationKind.trading, SimulationKind.monte_carlo} and self.trading is None:
            raise ValueError("Trading input is required")
        if self.kind not in {SimulationKind.trading, SimulationKind.monte_carlo} and not self.scenarios:
            raise ValueError("At least one scenario is required")
        return self


class SimulationResult(BaseModel):
    expected_value: float
    best_case: float
    worst_case: float
    confidence: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    probability_of_loss: float = Field(ge=0, le=1)
    risk_of_ruin: float = Field(ge=0, le=1)
    recommended_scenario: str | None = None
    metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class SimulationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    kind: SimulationKind
    state: SimulationState = SimulationState.queued
    scenarios: list[ScenarioInput]
    trading: TradingSimulationInput | None
    iterations: int
    seed: int | None
    created_by: str
    result: SimulationResult | None = None
    error: str | None = None
    live_environment_modified: bool = False
    automatic_order_execution: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SimulationListResponse(BaseModel):
    items: list[SimulationRecord]
    count: int


class SimulationPlatformStatus(BaseModel):
    total: int
    queued: int
    running: int
    completed: int
    failed: int
    sandbox_isolated: bool = True
    live_environment_modified: bool = False
    automatic_order_execution: bool = False
    automatic_merge: bool = False
