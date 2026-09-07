"""Telegram approval API.

Endpoints
---------
POST /v1/telegram-approvals/notify/{approval_request_id}  -> {"message_id": int}
POST /v1/telegram-approvals/notify-pending                 -> NotifyPendingResult
POST /v1/telegram-approvals/submit-and-notify               -> SubmitAndNotifyResult
POST /v1/telegram-approvals/webhook                        -> {"decision": str | None}

The webhook is what you register with Telegram's setWebhook call. None of
these routes ever places a broker order or sizes a position -- they only
ever call setup_submission.submit() and setup_submission.decide(), the same
two things a human could already do by hand through that router's own
endpoints. The buttons are a faster, mobile way to reach the exact same
gate, not a new one.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from app.setup_submission.models import SetupSubmissionRequest

from .models import NotifyPendingResult, SubmitAndNotifyResult
from .service import TelegramApprovalError, telegram_approval_service

router = APIRouter(prefix="/v1/telegram-approvals", tags=["telegram-approvals"])


@router.post("/notify/{approval_request_id}")
def notify(approval_request_id: UUID) -> dict:
    """Send the approval card for one pending setup."""
    try:
        message_id = telegram_approval_service.notify(approval_request_id)
    except TelegramApprovalError as exc:
        detail = str(exc)
        code = status.HTTP_404_NOT_FOUND if "unknown" in detail else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=code, detail=detail) from exc
    return {"message_id": message_id}


@router.post("/notify-pending", response_model=NotifyPendingResult)
def notify_pending() -> NotifyPendingResult:
    """Send a card for every setup still awaiting a decision. A single
    delivery failure never aborts the rest -- check the response's
    ``failed`` list rather than relying on this ever raising for that."""
    return telegram_approval_service.notify_pending()


@router.post("/submit-and-notify", response_model=SubmitAndNotifyResult)
def submit_and_notify(request: SetupSubmissionRequest) -> SubmitAndNotifyResult:
    """Evaluate accounts against a snapshot (exactly what
    /v1/setup-submission/submit does) and immediately send a card for every
    setup it produced. One call, and the phone lights up."""
    return telegram_approval_service.submit_and_notify(request)


@router.post("/webhook")
async def webhook(request: Request) -> dict:
    """Receives Telegram's Update payloads. Always returns 200 to Telegram
    for anything that is not an authorization/verification failure -- an
    update this module has nothing to do with (a plain text message, an
    edited message) is not an error, just a no-op."""
    raw = await request.json()
    try:
        decided = telegram_approval_service.handle_update(raw)
    except TelegramApprovalError as exc:
        # Authorization and signature failures are the one class of error
        # worth a non-200: they should be visible in Telegram's webhook
        # delivery logs, not silently swallowed as a no-op.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {"decision": decided.decision.value if decided else None}
