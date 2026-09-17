"""Instagram approval from a phone.

Endpoints
---------
GET  /v1/telegram-instagram/status
GET  /v1/telegram-instagram/audit
POST /v1/telegram-instagram/notify/{candidate_id}   -> {"message_id": int}
POST /v1/telegram-instagram/next                     -> NotifyResult
POST /v1/telegram-instagram/webhook                  -> {"status": str | None}

`next` is the one that matters day to day: it takes the next draft in
posting order (oldest shoot day first), writes its caption, and sends the
card. One draft per call, deliberately.

No route here publishes anything. Approving sets the candidate to
`approved`; the actual publish stays the separate call it already was, so
Brano can pick audio in the app and post Reels himself.

Telegram allows one webhook URL per bot. If this shares a bot with
telegram_approvals or telegram_live_execution, route all three through one
receiver that tries each module's verify_token in turn -- the action
alphabets are disjoint ({p,d} here, {a,r} and {x,c} there), so exactly one
can ever match.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from .models import InstagramAuditRecord, NotifyResult, TelegramInstagramStatus
from .service import TelegramInstagramError, telegram_instagram_service

router = APIRouter(prefix="/v1/telegram-instagram", tags=["telegram-instagram"])


@router.get("/status", response_model=TelegramInstagramStatus)
def telegram_instagram_status() -> TelegramInstagramStatus:
    return telegram_instagram_service.status()


@router.get("/audit", response_model=list[InstagramAuditRecord])
def audit(limit: int = 50) -> list[InstagramAuditRecord]:
    return telegram_instagram_service.audit_records(limit)


@router.post("/notify/{candidate_id}")
def notify(candidate_id: UUID) -> dict:
    try:
        return {"message_id": telegram_instagram_service.notify(candidate_id)}
    except TelegramInstagramError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/next", response_model=NotifyResult)
def finalize_next_and_notify(caption_draft: str | None = None) -> NotifyResult:
    """Next draft in posting order -> caption -> card on the phone.

    caption_draft is optional; omitted, AURON writes it itself via a real
    Anthropic call.
    """
    try:
        return telegram_instagram_service.finalize_next_and_notify(caption_draft)
    except TelegramInstagramError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/webhook")
async def webhook(request: Request) -> dict:
    """Telegram posts every update here. Anything that is not one of this
    module's button taps returns {"status": null} -- not an error, most
    updates are not taps."""
    try:
        decided = telegram_instagram_service.handle_update(await request.json())
    except TelegramInstagramError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {"status": decided.status.value if decided else None}
