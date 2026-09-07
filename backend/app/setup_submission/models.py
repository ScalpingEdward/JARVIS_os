"""Pydantic models for the setup-submission bridge.

These models describe the input (a market snapshot plus an optional account
filter), the individual submitted setups (one per executable account/strategy
pair that produced a trading setup) and the aggregate submission report.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from app.strategies.models import MarketSnapshot, TakeProfit, TradeSide


class SetupDecisionStatus(StrEnum):
    """Whether a human has actually looked at this setup.

    ``get_approval()`` used to return a SubmittedSetup with no notion of this
    at all -- any id present in the dict came back regardless of whether
    anyone had ever seen it, which meant "approval_request_id" was a name,
    not an enforced property. trade_risk_pipeline.assess() now refuses
    anything not explicitly ``approved`` -- see decide() below."""

    pending = "pending"
    approved = "approved"
    rejected = "rejected"


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
    decision: SetupDecisionStatus = SetupDecisionStatus.pending
    decided_by: str | None = Field(default=None, max_length=120)
    decided_at: datetime | None = None
    decision_note: str = Field(default="", max_length=500)


class SetupDecisionRequest(BaseModel):
    """Payload for POST /pending/{id}/decision. One-shot: a setup already
    decided (approved or rejected) refuses a second decision rather than
    silently overwriting who decided what."""

    decision: SetupDecisionStatus
    decided_by: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _decision_must_be_final(self) -> "SetupDecisionRequest":
        if self.decision == SetupDecisionStatus.pending:
            raise ValueError("decision must be 'approved' or 'rejected', not 'pending'")
        return self


class SetupSubmissionReport(BaseModel):
    """Aggregate result of a submission run."""

    symbol: str = Field(min_length=1, max_length=32)
    total_accounts_evaluated: int = Field(ge=0)
    total_executable_setups: int = Field(ge=0)
    total_submitted: int = Field(ge=0)
    submitted_setups: list[SubmittedSetup] = Field(default_factory=list)
    skipped_reason: str | None = Field(default=None, max_length=300)
