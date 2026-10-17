from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .gmail import GmailError
from .service import MailError, mail_service

router = APIRouter(prefix="/v1/mail", tags=["mail"])


@router.get("")
def overview(important_only: bool = False, days: int = 14) -> dict:
    """Sorted mail of the last days, pending reply drafts, and whether Gmail is connected."""
    return {**mail_service.status(), "items": mail_service.items(important_only, min(max(days, 1), 60)),
            "drafts": mail_service.drafts()}


@router.post("/poll")
def poll() -> dict:
    return mail_service.poll()


@router.post("/drafts/{draft_id}/send")
def send(draft_id: str) -> dict:
    """Brano's Send button. AURON's own tools cannot reach this."""
    try:
        return mail_service.send(draft_id)
    except MailError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except GmailError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/drafts/{draft_id}/discard")
def discard(draft_id: str) -> dict:
    try:
        return mail_service.discard(draft_id)
    except MailError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class DoneIn(BaseModel):
    done: bool = True


@router.post("/{mail_id}/done")
def done(mail_id: str, payload: DoneIn) -> dict:
    try:
        mail_service.mark_done(mail_id, payload.done)
    except MailError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True}
