from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .models import AutonomousCodeReviewCreate, CodeReviewExecuteRequest
from .service import autonomous_code_review_service

router = APIRouter(prefix="/v1/executive-autonomous-code-review", tags=["executive-autonomous-code-review"])


@router.get("/status")
def status(workspace_id: str = Query(...)):
    return autonomous_code_review_service.status(workspace_id)


@router.post("/reviews")
def create_review(payload: AutonomousCodeReviewCreate):
    try:
        return autonomous_code_review_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/reviews")
def list_reviews(workspace_id: str = Query(...)):
    return autonomous_code_review_service.list_records(workspace_id)


@router.get("/reviews/{record_id}")
def get_review(record_id: UUID, workspace_id: str = Query(...)):
    record = autonomous_code_review_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="code review record not found")
    return record


@router.post("/reviews/{record_id}/execute")
def execute_review(record_id: UUID, request: CodeReviewExecuteRequest, workspace_id: str = Query(...)):
    try:
        return autonomous_code_review_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(...)):
    return autonomous_code_review_service.audit_records(workspace_id)
