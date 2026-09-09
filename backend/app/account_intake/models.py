from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AccountIntakeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    requester_id: str = Field(min_length=1, max_length=100)


class ProposedAccountFields(BaseModel):
    """What was actually extracted, always shown back before anything is
    registered -- if the extraction got something wrong, this is where a
    human catches it, not after the fact."""

    label: str
    broker: str
    login: str
    server: str
    account_type: str  # "demo" | "live" | "prop" -- kept as str here since
    # extraction is inherently best-effort; AccountIntakeService.confirm()
    # validates it against the real AccountType enum before registering.
    currency: str = "USD"
    initial_balance: float | None = None
    strategy_id: str | None = None


class AccountProposal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    requester_id: str
    fields: ProposedAccountFields
    missing_fields: list[str] = Field(default_factory=list)
    confirmed: bool = False
    registered_account_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AccountIntakeRefusal(BaseModel):
    """What comes back instead of a proposal when the message itself
    can't safely be processed -- see credential_guard.py."""

    reason: str
