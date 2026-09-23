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


@router.get("/schedule")
def schedule_status() -> dict:
    """What the posting schedule will do next, and whether it is running at
    all -- otherwise "it is enabled" is a claim nobody can check."""
    from datetime import datetime, timedelta

    from .schedule import _timezone, posting_scheduler, slot_for, waiting_for_a_decision

    now = datetime.now(_timezone())
    return {
        "running": posting_scheduler.is_running,
        "now": now.isoformat(timespec="seconds"),
        "today": f"{slot_for(now.date()).hour:02d}:{slot_for(now.date()).minute:02d} "
                 f"{slot_for(now.date()).kind}",
        "tomorrow": f"{slot_for(now.date() + timedelta(days=1)).kind}",
        "already_fired_today": [
            f"{hour:02d}:{minute:02d}"
            for (day, hour, minute) in posting_scheduler.fired_slots
            if day == now.date()
        ],
        "a_card_is_waiting_for_a_decision": waiting_for_a_decision(),
    }


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
