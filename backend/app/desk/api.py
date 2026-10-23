from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import service

router = APIRouter(prefix="/v1/desk", tags=["desk"])


class ReportIn(BaseModel):
    result: dict | None = None
    error: str | None = None
    approve: str | None = None     # the runner: this one needs Brano's click, and why


class ApproveIn(BaseModel):
    ok: bool


@router.post("/runner/claim")
def runner_claim() -> list[dict]:
    """tools/desk_runner.py, every half second: what to do at the laptop."""
    return service.claim()


@router.post("/runner/{cmd_id}")
def runner_report(cmd_id: int, body: ReportIn) -> dict:
    try:
        return service.report(cmd_id, body.result, body.error, body.approve)
    except service.DeskError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/waiting")
def waiting() -> list[dict]:
    """Sensitive steps waiting for Brano -- every dashboard asks him (desk.js)."""
    return service.waiting()


@router.post("/{cmd_id}/approve")
def approve(cmd_id: int, body: ApproveIn) -> dict:
    """Brano's click on the dashboard. AURON has no way to call this."""
    try:
        return service.approve(cmd_id, body.ok)
    except service.DeskError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
