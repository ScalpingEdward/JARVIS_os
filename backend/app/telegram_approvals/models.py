from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.setup_submission.models import SetupSubmissionReport


@dataclass(frozen=True)
class TelegramApprovalConfig:
    """The signing secret for callback tokens, plus the chat allowed to
    decide anything. Both from the environment, never a default -- same
    discipline as every other credential-backed component in this build.

    A dedicated secret rather than reusing the bot token: callback_data is
    fully attacker-controllable (anyone who can message the bot can set it
    to anything), so it needs to be signed with something an outsider has no
    way to obtain. The chat_id allowlist is the first line of defense --
    only Brano's own chat with the bot ever sees the buttons at all -- the
    signature is defense in depth on top of that, cheap to add and worth it
    given what a tap here ultimately authorises (real position sizing and
    tracking downstream, even though it still stops short of a broker order).
    """

    callback_secret: str | None = field(default_factory=lambda: os.getenv("TELEGRAM_CALLBACK_SECRET"))
    allowed_chat_id: str | None = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID"))
    #: Off by default, deliberately. Tapping Approve always records the
    #: decision -- that part is unconditional. Whether a tap should *also*
    #: immediately run risk sizing, open a tracked position, and start
    #: supervision (advance_to_preflight) is a bigger behavioral commitment
    #: than the buttons themselves: it creates real, persisted records the
    #: moment you tap, not just an approval note. Set
    #: TELEGRAM_AUTO_ADVANCE=true once you want that; until then, advancing
    #: stays an explicit separate call.
    auto_advance: bool = field(
        default_factory=lambda: os.getenv("TELEGRAM_AUTO_ADVANCE", "").lower() in ("1", "true", "yes")
    )


class TelegramWebhookUpdate(BaseModel):
    """The minimal slice of a Telegram Update this module reads. Extra
    fields Telegram sends are ignored, not rejected -- pydantic's default
    behavior, and correct here since Telegram's schema is outside our
    control and adds fields over time."""

    update_id: int
    callback_query: dict[str, Any] | None = None


class NotifyOutcome(BaseModel):
    approval_request_id: UUID
    message_id: int | None = None
    error: str | None = None


class NotifyPendingResult(BaseModel):
    sent: list[NotifyOutcome]
    failed: list[NotifyOutcome]


class SubmitAndNotifyResult(BaseModel):
    report: SetupSubmissionReport
    notified: NotifyPendingResult


class TelegramApprovalStatus(BaseModel):
    """Capability health, not just "are the env vars set" -- bot_reachable
    is a real getMe() call, so a bot token that is present but wrong (a
    typo, a revoked token) shows up here rather than only failing the
    first time someone actually taps a button."""

    callback_secret_configured: bool
    allowed_chat_configured: bool
    auto_advance: bool
    bot_reachable: bool | None = None
    bot_username: str | None = None
    error: str | None = None


class TelegramAuditRecord(BaseModel):
    """One thing this module did or refused, kept for later review -- same
    shape as the AuditRecord already used across the executive_mt5_*
    modules (workspace_id/record_id/action/actor_id/created_at), adapted
    to this module's own domain: notify()/notify_pending() sending cards,
    and handle_update() processing (or refusing) a tap."""

    id: UUID = Field(default_factory=uuid4)
    approval_request_id: UUID | None = None
    action: str  # "notify" | "decision" | "unauthorized_chat" | "invalid_token"
    success: bool
    detail: str = ""
    #: Telegram username or user id for an inbound event (a tap); unset
    #: for an outbound notify(), which has no "who" to attribute to.
    actor: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
