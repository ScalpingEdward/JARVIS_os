from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class TelegramInstagramConfig:
    """Its own signing secret, and the one chat allowed to decide anything.

    Separate from the trading modules' secrets on purpose: a tap here
    approves something that ends up publicly visible under Brano's name,
    which is a different kind of consequence than a trade, not a smaller
    one. Neither secret should be able to forge the other's buttons.
    """

    callback_secret: str | None = field(
        default_factory=lambda: os.getenv("TELEGRAM_INSTAGRAM_CALLBACK_SECRET")
    )
    allowed_chat_id: str | None = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID"))


class TelegramWebhookUpdate(BaseModel):
    """The slice of a Telegram Update this module reads. Unknown fields are
    ignored rather than rejected -- Telegram's schema is outside our control
    and grows over time."""

    update_id: int
    callback_query: dict[str, Any] | None = None


class TelegramInstagramStatus(BaseModel):
    """What is configured and whether the bot is reachable. Never sends
    anything -- safe to poll."""

    callback_secret_configured: bool
    allowed_chat_configured: bool
    bot_reachable: bool | None = None
    bot_username: str | None = None
    pending_drafts: int = 0
    candidates_awaiting_decision: int = 0
    error: str | None = None


class InstagramAuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    candidate_id: UUID | None = None
    action: str
    success: bool
    detail: str = ""
    actor: str | None = None


class NotifyResult(BaseModel):
    candidate_id: UUID
    message_id: int | None = None
    error: str | None = None
    #: Set when the card came from finalizing a draft rather than from an
    #: existing candidate -- says which draft was consumed.
    from_draft_id: UUID | None = None
