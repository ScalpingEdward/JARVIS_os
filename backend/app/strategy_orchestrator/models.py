"""Models for strategy orchestrator responses."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from ..accounts.models import AccountStatus, AccountType
from ..strategies.models import StrategyResult


class AccountStrategyEvaluation(BaseModel):
    """Result of evaluating all assigned strategies for a single account."""

    account_id: UUID
    login: int
    account_type: AccountType
    status: AccountStatus
    assigned_strategies: list[str] = Field(
        default_factory=list,
        description="Strategy IDs assigned to this account",
    )
    strategy_results: list[StrategyResult] = Field(
        default_factory=list,
        description="Evaluation results for all assigned strategies",
    )
    valid_setups: list[StrategyResult] = Field(
        default_factory=list,
        description="Filtered to only results with valid setups",
    )
    compliance_ok: bool = Field(
        description="Whether the account is compliant (not breached, active)"
    )
    executable_setups: list[StrategyResult] = Field(
        default_factory=list,
        description="Valid setups that pass compliance (safe to execute)",
    )
    blocked_reason: str | None = Field(
        default=None,
        description="Reason why setups are blocked (if compliance_ok=False)",
    )


class OrchestrationResult(BaseModel):
    """Complete orchestration result for all accounts."""

    symbol: str
    total_accounts: int
    active_accounts: int
    total_evaluations: int = Field(
        description="Total number of strategy evaluations across all accounts"
    )
    total_valid_setups: int = Field(
        description="Total valid setups before compliance filtering"
    )
    total_executable_setups: int = Field(
        description="Total setups that pass compliance and are safe to execute"
    )
    account_evaluations: list[AccountStrategyEvaluation] = Field(
        default_factory=list,
        description="Per-account evaluation results",
    )
