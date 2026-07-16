from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AccountType(str, Enum):
    funded = "funded"
    live = "live"
    demo = "demo"


class RiskState(str, Enum):
    normal = "normal"
    warning = "warning"
    critical = "critical"
    blocked = "blocked"


class PositionSnapshot(BaseModel):
    symbol: str = Field(min_length=2, max_length=30)
    direction: str = Field(pattern="^(long|short)$")
    notional: float = Field(ge=0)
    floating_pnl: float = 0.0
    strategy: str = Field(default="manual", min_length=2, max_length=80)


class AccountSnapshotCreate(BaseModel):
    account_name: str = Field(min_length=2, max_length=100)
    account_type: AccountType
    provider: str = Field(min_length=2, max_length=80)
    balance: float = Field(gt=0)
    equity: float = Field(gt=0)
    day_start_balance: float = Field(gt=0)
    initial_balance: float = Field(gt=0)
    daily_drawdown_limit_pct: float = Field(default=5.0, gt=0, le=100)
    max_drawdown_limit_pct: float = Field(default=10.0, gt=0, le=100)
    positions: list[PositionSnapshot] = Field(default_factory=list)


class AccountSnapshot(AccountSnapshotCreate):
    id: UUID = Field(default_factory=uuid4)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    daily_drawdown_pct: float
    total_drawdown_pct: float
    risk_state: RiskState


class StressScenario(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    symbol_shocks_pct: dict[str, float] = Field(default_factory=dict)


class PortfolioReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    owner_name: str = "MASTER Brano"
    accounts: list[AccountSnapshot]
    total_balance: float
    total_equity: float
    floating_pnl: float
    gross_exposure: float
    symbol_exposure: dict[str, float]
    strategy_exposure: dict[str, float]
    concentration_pct: float
    portfolio_risk_state: RiskState
    warnings: list[str]
    recommendations: list[str]
    requires_human_approval: bool = True
    automatic_execution: bool = False
    automatic_order_execution: bool = False


class StressResult(BaseModel):
    scenario: str
    projected_pnl: float
    projected_equity: float
    projected_drawdown_pct: float
    risk_state: RiskState
    warnings: list[str]
    requires_human_approval: bool = True
    automatic_execution: bool = False


class PortfolioRiskStatus(BaseModel):
    service: str = "portfolio-risk"
    owner_name: str = "MASTER Brano"
    account_count: int
    automatic_execution: bool = False
    automatic_order_execution: bool = False
