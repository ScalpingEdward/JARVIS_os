from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class TelegramLiveExecutionConfig:
    """A dedicated secret and, optionally, a dedicated chat -- deliberately
    not reused from telegram_approvals's own config. This module's tap
    is the one action in the whole system that can end in a real broker
    order; a leak of the setup-approval secret must never be enough to
    forge a tap here too.

    allowed_chat_id falls back to TELEGRAM_CHAT_ID (the same phone Brano
    already approves setups from) if TELEGRAM_LIVE_EXECUTION_CHAT_ID is
    not set separately -- convenient by default, still overridable for
    anyone who wants execution approvals routed to a different chat.
    """

    callback_secret: str | None = field(
        default_factory=lambda: os.getenv("TELEGRAM_LIVE_EXECUTION_CALLBACK_SECRET")
    )
    allowed_chat_id: str | None = field(
        default_factory=lambda: os.getenv("TELEGRAM_LIVE_EXECUTION_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
    )


class TelegramWebhookUpdate(BaseModel):
    """The minimal slice of a Telegram Update this module reads."""

    update_id: int
    callback_query: dict[str, Any] | None = None


class NotifyOutcome(BaseModel):
    record_id: UUID
    message_id: int | None = None
    error: str | None = None


class NotifyPendingResult(BaseModel):
    sent: list[NotifyOutcome]
    failed: list[NotifyOutcome]


class TelegramLiveExecutionStatus(BaseModel):
    """Capability health -- a real getMe() call, not just an env-var
    presence check, so a wrong or revoked bot token shows up here rather
    than only failing the first time an order is actually ready."""

    callback_secret_configured: bool
    allowed_chat_configured: bool
    bot_reachable: bool | None = None
    bot_username: str | None = None
    error: str | None = None


class TelegramLiveExecutionAuditRecord(BaseModel):
    """One thing this module did or refused, kept for later review. A
    stricter, separate trail from telegram_approvals's own audit log --
    this one only ever records events that could plausibly have ended
    with a real order reaching a real broker."""

    id: UUID = Field(default_factory=uuid4)
    record_id: UUID | None = None
    action: str  # "notify" | "execute" | "cancel" | "unauthorized_chat" | "invalid_token" | "stale_state"
    success: bool
    detail: str = ""
    actor: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
