from fastapi import APIRouter, HTTPException

from .models import CopierEquityPoint, CopierOverview, CopierStatus, CopierStatusIn
from .service import CopierStatusError, copier_status_service

router = APIRouter(prefix="/v1/copier", tags=["copier"])


@router.post("/status", response_model=CopierStatus)
def push_status(payload: CopierStatusIn) -> CopierStatus:
    """Called by each copier profile every 15 seconds."""
    return copier_status_service.push(payload)


@router.get("/status", response_model=list[CopierStatus])
def list_status() -> list[CopierStatus]:
    return copier_status_service.list()


@router.get("/overview", response_model=CopierOverview)
def overview() -> CopierOverview:
    """Totals per currency, every account, and every group across accounts."""
    return copier_status_service.overview()


@router.get("/history", response_model=dict[str, list[CopierEquityPoint]])
def history(hours: float = 24) -> dict[str, list[CopierEquityPoint]]:
    """Balance and equity per profile, one point every five minutes -- for the dashboard's curves."""
    return copier_status_service.history(min(max(hours, 1), 24 * 30))


@router.delete("/status/{profile}", status_code=204)
def forget(profile: str) -> None:
    """Drop a profile that no longer exists. Nothing in MT5 is touched."""
    try:
        copier_status_service.forget(profile)
    except CopierStatusError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
