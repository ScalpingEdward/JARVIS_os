from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class DeploymentState(str, Enum):
    blocked = "blocked"
    hold = "hold"
    diversify = "diversify"
    fund_reduced = "fund-reduced"
    fund_full = "fund-full"


class AccountType(str, Enum):
    live = "live"
    prop = "prop"


class BrokerCandidate(BaseModel):
    broker_id: str = Field(min_length=1, max_length=100)
    account_id: str = Field(min_length=1, max_length=100)
    account_type: AccountType = AccountType.live
    base_currency: str = Field(min_length=3, max_length=8)
    regulated: bool = True
    withdrawals_verified: bool = False
    operational_health: int = Field(default=50, ge=0, le=100)
    current_owned_balance: float = Field(default=0, ge=0)
    requested_funding: float = Field(default=0, ge=0)


class BrokerDeploymentPolicy(BaseModel):
    max_broker_share: float = Field(default=0.50, gt=0, le=1)
    max_account_share: float = Field(default=0.40, gt=0, le=1)
    minimum_operational_health: int = Field(default=70, ge=0, le=100)
    require_regulation: bool = True
    require_verified_withdrawal: bool = True
    max_new_accounts_per_cycle: int = Field(default=1, ge=1, le=10)


class LiveCapitalDeploymentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    treasury_approved_live_capital: float = Field(ge=0)
    human_approved: bool = False
    risk_brain_clear: bool = True
    candidates: list[BrokerCandidate] = Field(min_length=1)
    policy: BrokerDeploymentPolicy

    @model_validator(mode="after")
    def validate_live_only(self):
        if any(candidate.account_type != AccountType.live for candidate in self.candidates):
            raise ValueError("Prop accounts are forbidden in Live capital deployment")
        return self


class FundingLine(BaseModel):
    broker_id: str
    account_id: str
    base_currency: str
    requested_funding: float
    approved_funding: float
    allocation_share: float
    deployable: bool
    action: str
    reasons: list[str]


class DeploymentScores(BaseModel):
    broker_diversification: int = Field(ge=0, le=100)
    concentration_safety: int = Field(ge=0, le=100)
    operational_readiness: int = Field(ge=0, le=100)
    funding_efficiency: int = Field(ge=0, le=100)
    deployment_confidence: int = Field(ge=0, le=100)


class LiveCapitalDeploymentAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    state: DeploymentState
    approved_treasury_capital: float
    approved_deployment_capital: float
    unallocated_capital: float
    funding_lines: list[FundingLine]
    scores: DeploymentScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeploymentStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: DeploymentState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
