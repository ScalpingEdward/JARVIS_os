from fastapi import APIRouter, HTTPException, Query

from .models import AuditEvent, ResilienceReviewAction, ResilienceReviewCreate, ResilienceReviewRecord
from .service import PostIncidentResilienceError, service

router = APIRouter(prefix="/v1/post-incident-resilience", tags=["post-incident-resilience"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "post-incident-resilience", "version": "21.27", "status": "ready"}


@router.post("/reviews", response_model=ResilienceReviewRecord)
def create_review(payload: ResilienceReviewCreate) -> ResilienceReviewRecord:
    try:
        return service.create(payload)
    except PostIncidentResilienceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/reviews", response_model=list[ResilienceReviewRecord])
def list_reviews(workspace_id: str = Query(min_length=1)) -> list[ResilienceReviewRecord]:
    return service.list(workspace_id)


@router.get("/reviews/{record_id}", response_model=ResilienceReviewRecord)
def get_review(record_id: str, workspace_id: str = Query(min_length=1)) -> ResilienceReviewRecord:
    try:
        return service.get(record_id, workspace_id)
    except PostIncidentResilienceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reviews/{record_id}/actions", response_model=ResilienceReviewRecord)
def act_on_review(
    record_id: str,
    action: ResilienceReviewAction,
    workspace_id: str = Query(min_length=1),
) -> ResilienceReviewRecord:
    try:
        return service.act(record_id, workspace_id, action)
    except PostIncidentResilienceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)
