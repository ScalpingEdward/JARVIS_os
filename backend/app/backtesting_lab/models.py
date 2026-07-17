from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class BacktestStatus(str, Enum):
    queued = "queued"
    completed = "completed"
    failed = "failed"


class SplitMode(str, Enum):
    full_sample = "full_sample"
    walk_forward = "walk_forward"


class BacktestDataset(BaseModel):
    symbol: str = Field(min_length=2, max_length=40)
    timeframe: str = Field(min_length=2, max_length=12)
    bars: int = Field(ge=100, le=10_000_000)
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_dates(self) -> "BacktestDataset":
        if self.end <= self.start:
            raise ValueError("dataset end must be after start")
        return self


class CostModel(BaseModel):
    spread_points: float = Field(default=0.0, ge=0)
    slippage_points: float = Field(default=0.0, ge=0)
    commission_per_lot: float = Field(default=0.0, ge=0)


class BacktestJobCreate(BaseModel):
    strategy_id: UUID
    strategy_version: int = Field(ge=1)
    dataset: BacktestDataset
    initial_balance: float = Field(default=10_000, gt=0)
    risk_per_trade_pct: float = Field(default=1.0, gt=0, le=5)
    split_mode: SplitMode = SplitMode.full_sample
    train_ratio: float = Field(default=0.7, ge=0.5, le=0.9)
    costs: CostModel = Field(default_factory=CostModel)


class BacktestMetrics(BaseModel):
    net_profit_pct: float
    max_drawdown_pct: float = Field(ge=0)
    win_rate_pct: float = Field(ge=0, le=100)
    profit_factor: float = Field(ge=0)
    expectancy_r: float
    trades: int = Field(ge=0)
    sharpe_ratio: float
    stability_score: float = Field(ge=0, le=100)


class BacktestJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    owner_name: str = "MASTER Brano"
    status: BacktestStatus = BacktestStatus.completed
    request: BacktestJobCreate
    metrics: BacktestMetrics
    warnings: list[str] = Field(default_factory=list)
    human_approval_required: bool = True
    automatic_execution: bool = False
    automatic_order_execution: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BacktestComparisonRequest(BaseModel):
    job_ids: list[UUID] = Field(min_length=2, max_length=20)


class BacktestComparison(BaseModel):
    ranked_job_ids: list[UUID]
    best_job_id: UUID
    rationale: list[str]
    human_approval_required: bool = True
    automatic_execution: bool = False


class BacktestingLabStatus(BaseModel):
    owner_name: str = "MASTER Brano"
    jobs: int
    completed_jobs: int
    automatic_execution: bool = False
    automatic_order_execution: bool = False
