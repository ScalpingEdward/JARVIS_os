from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    HOLD = "hold"
    BLOCKED = "blocked"


class TradeApprovalCreate(BaseModel):
    account_id: str = Field(min_length=1, max_length=80)
    symbol: str = Field(min_length=1, max_length=40)
    direction: str = Field(pattern="^(long|short)$")
    setup_tag: str = Field(min_length=1, max_length=80)
    requested_risk_amount: float = Field(gt=0)
    allocated_risk_amount: float = Field(ge=0)
    reward_to_risk: float = Field(gt=0, le=100)
    playbook_approved: bool
    daily_drawdown_safe: bool
    total_drawdown_safe: bool
    spread_safe: bool = True
    news_window_clear: bool = True
    correlation_safe: bool = True
    global_kill_switch: bool = False
    manual_approval: bool = False
    automatic_execution: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "TradeApprovalCreate":
        if self.automatic_execution:
            raise ValueError("automatic execution is disabled")
        return self


class ApprovalCheck(BaseModel):
    check: str
    passed: bool
    severity: str
    message: str


class TradeApprovalRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    account_id: str
    symbol: str
    direction: str
    setup_tag: str
    requested_risk_amount: float
    allocated_risk_amount: float
    reward_to_risk: float
    decision: ApprovalDecision
    checks: list[ApprovalCheck]
    blockers: list[str]
    manual_approval_required: bool = True
    automatic_execution: bool = False
    execution_permitted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KillSwitchState(BaseModel):
    active: bool = False
    reason: str = ""
    activated_at: datetime | None = None


class KillSwitchUpdate(BaseModel):
    active: bool
    reason: str = Field(default="", max_length=500)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_approval(self) -> "KillSwitchUpdate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.active and not self.reason.strip():
            raise ValueError("a reason is required when activating the kill switch")
        return self


class TradeApprovalStatus(BaseModel):
    service: str = "trade-approval"
    version: str = "7.5"
    approval_gateway_enabled: bool = True
    global_kill_switch_enabled: bool = True
    advisory_only: bool = True
    automatic_execution: bool = False
    human_approval_required: bool = True
