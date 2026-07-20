from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, PersistentEventStoreAssessment, PersistentEventStoreAssessmentCreate, PersistentEventStoreStatusResponse
from .service import executive_persistent_event_store_service

router = APIRouter(tags=["executive-persistent-event-store"])
BASE = "/v1/executive-persistent-event-store"


@router.get(f"{BASE}/status", response_model=PersistentEventStoreStatusResponse)
def persistent_event_store_status(workspace_id: str = Query(min_length=1, max_length=100)) -> PersistentEventStoreStatusResponse:
    return executive_persistent_event_store_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=PersistentEventStoreAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: PersistentEventStoreAssessmentCreate) -> PersistentEventStoreAssessment:
    try:
        return executive_persistent_event_store_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[PersistentEventStoreAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[PersistentEventStoreAssessment]:
    return executive_persistent_event_store_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=PersistentEventStoreAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> PersistentEventStoreAssessment:
    item = executive_persistent_event_store_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Persistent event-store assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def persistent_event_store_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_persistent_event_store_service.audit(workspace_id)
