from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, TransactionalOutboxAssessment, TransactionalOutboxAssessmentCreate, TransactionalOutboxStatusResponse
from .service import executive_transactional_outbox_service

router = APIRouter(tags=["executive-transactional-outbox"])
BASE = "/v1/executive-transactional-outbox"


@router.get(f"{BASE}/status", response_model=TransactionalOutboxStatusResponse)
def transactional_outbox_status(workspace_id: str = Query(min_length=1, max_length=100)) -> TransactionalOutboxStatusResponse:
    return executive_transactional_outbox_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=TransactionalOutboxAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: TransactionalOutboxAssessmentCreate) -> TransactionalOutboxAssessment:
    try:
        return executive_transactional_outbox_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[TransactionalOutboxAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[TransactionalOutboxAssessment]:
    return executive_transactional_outbox_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=TransactionalOutboxAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> TransactionalOutboxAssessment:
    item = executive_transactional_outbox_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Transactional outbox assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def transactional_outbox_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_transactional_outbox_service.audit(workspace_id)
