"""Pydantic models for the setup-submission bridge.

These models describe the input (a market snapshot plus an optional account
filter), the individual submitted setups (one per executable account/strategy
pair that produced a trading setup) and the aggregate submission report.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from app.strategies.models import MarketSnapshot, TakeProfit, TradeSide


class SetupSubmissionRequest(BaseModel):
    """Input for a submission run.

    Carries the full :class:`MarketSnapshot` to evaluate and, optionally, a list
    of account IDs to restrict the run to. ``symbol`` is derived from the
    snapshot; if supplied explicitly it must match the snapshot's symbol
    (fail-closed to avoid silently evaluating the wrong instrument).
    """

    snapshot: MarketSnapshot
    account_ids: list[UUID] | None = Field(
        default=None,
        description="Optional filter — only these accounts are evaluated. None = all accounts.",
    )
    symbol: str | None = Field(
        default=None,
        max_length=32,
        description="Optional; defaults to the snapshot's symbol. Must match it if provided.",
    )

    @model_validator(mode="after")
    def _sync_symbol(self) -> "SetupSubmissionRequest":
        if self.symbol is None:
            self.symbol = self.snapshot.symbol
        elif self.symbol != self.snapshot.symbol:
            raise ValueError(
                f"symbol {self.symbol!r} does not match snapshot symbol {self.snapshot.symbol!r}"
            )
        return self


class SubmittedSetup(BaseModel):
    """A single trading setup that has been submitted to the approval gate.

    One is produced for every executable account/strategy pair whose strategy
    generated a setup against the snapshot. ``approval_request_id`` uniquely
    identifies the pending approval request created for it.
    """

    account_id: UUID
    login: str = Field(min_length=1, max_length=60)
    strategy_id: str = Field(min_length=1, max_length=80)
    symbol: str = Field(min_length=1, max_length=32)
    side: TradeSide
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profits: list[TakeProfit] = Field(min_length=1, max_length=5)
    risk_reward: float = Field(gt=0)
    confidence: float = Field(ge=0, le=100)
    reasoning: str = Field(default="", max_length=500)
    approval_request_id: UUID = Field(default_factory=uuid4)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SetupSubmissionReport(BaseModel):
    """Aggregate result of a submission run."""

    symbol: str = Field(min_length=1, max_length=32)
    total_accounts_evaluated: int = Field(ge=0)
    total_executable_setups: int = Field(ge=0)
    total_submitted: int = Field(ge=0)
    submitted_setups: list[SubmittedSetup] = Field(default_factory=list)
    skipped_reason: str | None = Field(default=None, max_length=300)
