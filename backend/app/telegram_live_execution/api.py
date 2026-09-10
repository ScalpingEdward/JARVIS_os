"""Telegram live-execution API -- the final "place the real order" gate.

Endpoints
---------
GET  /v1/telegram-live-execution/status
GET  /v1/telegram-live-execution/audit
POST /v1/telegram-live-execution/notify/{record_id}       -> {"message_id": int}
POST /v1/telegram-live-execution/notify-pending             -> NotifyPendingResult
POST /v1/telegram-live-execution/webhook                    -> {"state": str | None}

Register this webhook's URL with Telegram separately from
telegram_approvals's own webhook (a distinct bot, or the same bot with a
different path -- Telegram only supports one webhook URL per bot, so if
reusing the same bot as telegram_approvals, route both through one
webhook receiver that dispatches by trying each module's verify_token in
turn; see docs/n8n-instagram-setup.md's own notes on separating concerns
for the equivalent Instagram decision, though this is a Telegram-side,
not an n8n-side, wiring question).

None of these routes place a broker order directly -- they only ever call
live_order_executor_service.get()/list_records()/execute(), the same
calls a human already makes by hand today via curl or PowerShell. The
buttons are a faster, mobile way to reach the exact same gate.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from .models import NotifyPendingResult, TelegramLiveExecutionAuditRecord, TelegramLiveExecutionStatus
from .service import TelegramLiveExecutionError, telegram_live_execution_service

router = APIRouter(prefix="/v1/telegram-live-execution", tags=["telegram-live-execution"])


@router.get("/status", response_model=TelegramLiveExecutionStatus)
def telegram_live_execution_status() -> TelegramLiveExecutionStatus:
    return telegram_live_execution_service.status()


@router.get("/audit", response_model=list[TelegramLiveExecutionAuditRecord])
def audit(limit: int = 50) -> list[TelegramLiveExecutionAuditRecord]:
    return telegram_live_execution_service.audit_records(limit)


@router.post("/notify/{record_id}")
def notify(record_id: UUID) -> dict:
    """Send the execute/cancel card for one order sitting in
    approval-required. Refuses for any other state."""
    try:
        message_id = telegram_live_execution_service.notify(record_id)
    except TelegramLiveExecutionError as exc:
        detail = str(exc)
        code = status.HTTP_404_NOT_FOUND if "unknown" in detail else (
            status.HTTP_409_CONFLICT if "not approval-required" in detail else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=code, detail=detail) from exc
    return {"message_id": message_id}


@router.post("/notify-pending", response_model=NotifyPendingResult)
def notify_pending(workspace_id: str = Query(min_length=1, max_length=100)) -> NotifyPendingResult:
    """Send a card for every order in this workspace currently waiting on
    exactly this decision."""
    return telegram_live_execution_service.notify_pending(workspace_id)


@router.post("/webhook")
async def webhook(request: Request) -> dict:
    """Receives Telegram's Update payloads for this module's buttons.
    Always returns 200 for anything not an authorization/verification
    failure -- an update this module has nothing to do with is a no-op,
    not an error."""
    raw = await request.json()
    try:
        result = telegram_live_execution_service.handle_update(raw)
    except TelegramLiveExecutionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {"state": result.state.value if result else None}
