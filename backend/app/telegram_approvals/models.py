from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import BaseModel

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
