from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class GovernorState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    MONITORING = "monitoring"
    ACTION_REQUIRED = "action-required"
    KILL_SWITCH = "kill-switch"
    RECOVERY_PENDING = "recovery-pending"
    APPROVAL_REQUIRED = "approval-required"
    RECOVERY_READY = "recovery-ready"
    ACTIVE = "active"
    ARCHIVED = "archived"
    FAILED = "failed"


class PortfolioSnapshot(BaseModel):
    account_equity: float = Field(gt=0)
    daily_drawdown_pct: float = Field(ge=0)
    total_drawdown_pct: float = Field(ge=0)
    portfolio_heat_pct: float = Field(ge=0)
    margin_level_pct: float = Field(ge=0)
    correlated_exposure_pct: float = Field(ge=0)
    open_positions: int = Field(ge=0)
    spread_multiplier: float = Field(ge=0)
    broker_latency_ms: int = Field(ge=0)
    data_feed_healthy: bool = True
    vps_healthy: bool = True
    market_allowed_by_v19_08: bool = False
    shadow_validated_by_v19_09: bool = False
    journal_validated_by_v19_10: bool = False
    optimizer_approved_by_v19_11: bool = False


class GovernorLimits(BaseModel):
    max_daily_drawdown_pct: float = Field(gt=0)
    max_total_drawdown_pct: float = Field(gt=0)
    max_portfolio_heat_pct: float = Field(gt=0)
    min_margin_level_pct: float = Field(gt=0)
    max_correlated_exposure_pct: float = Field(gt=0)
    max_spread_multiplier: float = Field(gt=0)
    max_broker_latency_ms: int = Field(gt=0)


class PortfolioGovernorCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    upstream_risk_brain_blocked: bool = False
    account_risk_approved: bool = False
    prop_rules_approved: bool = False
    human_approved: bool = False
    snapshot: PortfolioSnapshot
    limits: GovernorLimits


class GovernorExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(activate-kill-switch|prepare-recovery|approve-recovery|resume|archive)$")
    human_approved: bool | None = None


class GovernorAction(BaseModel):
    action: str
    reason: str
    automatic: bool


class PortfolioGovernorRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: GovernorState
    detail: str
    request: PortfolioGovernorCreate
    actions: list[GovernorAction] = Field(default_factory=list)
    breaches: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PortfolioGovernorStatus(BaseModel):
    module: str = "executive-autonomous-portfolio-governor"
    version: str = "19.12"
    workspace_id: str
    total_records: int
    active_records: int
    kill_switch_records: int
    recovery_records: int


class PortfolioGovernorAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: GovernorState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
