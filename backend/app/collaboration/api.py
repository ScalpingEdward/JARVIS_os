from uuid import UUID

from fastapi import APIRouter, HTTPException

from .models import CollaborationCreate, CollaborationList, CollaborationRecord, ContributionCreate, ReviewCreate
from .service import CollaborationError, collaboration_service

router = APIRouter(prefix="/v1/collaboration", tags=["collaboration"])


def _call(operation):
    try:
        return operation()
    except CollaborationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions", response_model=CollaborationRecord)
def create_session(payload: CollaborationCreate) -> CollaborationRecord:
    return _call(lambda: collaboration_service.create(payload))


@router.get("/sessions", response_model=CollaborationList)
def list_sessions() -> CollaborationList:
    items = collaboration_service.list_all()
    return CollaborationList(items=items, count=len(items))


@router.get("/sessions/{session_id}", response_model=CollaborationRecord)
def get_session(session_id: UUID) -> CollaborationRecord:
    return _call(lambda: collaboration_service.get(session_id))


@router.post("/sessions/{session_id}/contributions", response_model=CollaborationRecord)
def contribute(session_id: UUID, payload: ContributionCreate) -> CollaborationRecord:
    return _call(lambda: collaboration_service.contribute(session_id, payload))


@router.post("/sessions/{session_id}/contributions/{contribution_id}/reviews", response_model=CollaborationRecord)
def review(session_id: UUID, contribution_id: UUID, payload: ReviewCreate) -> CollaborationRecord:
    return _call(lambda: collaboration_service.review(session_id, contribution_id, payload))


@router.get("/sessions/{session_id}/compare")
def compare(session_id: UUID) -> dict[str, object]:
    return _call(lambda: collaboration_service.compare(session_id))
