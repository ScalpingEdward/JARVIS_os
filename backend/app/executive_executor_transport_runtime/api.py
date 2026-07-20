from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ExecutorTransportAssessment, ExecutorTransportAssessmentCreate, ExecutorTransportStatusResponse
from .service import executive_executor_transport_runtime_service

router = APIRouter(tags=["executive-executor-transport-runtime"])
BASE = "/v1/executive-executor-transport-runtime"


@router.get(f"{BASE}/status", response_model=ExecutorTransportStatusResponse)
def transport_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutorTransportStatusResponse:
    return executive_executor_transport_runtime_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=ExecutorTransportAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: ExecutorTransportAssessmentCreate) -> ExecutorTransportAssessment:
    try:
        return executive_executor_transport_runtime_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[ExecutorTransportAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[ExecutorTransportAssessment]:
    return executive_executor_transport_runtime_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=ExecutorTransportAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutorTransportAssessment:
    item = executive_executor_transport_runtime_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executor transport assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def transport_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_executor_transport_runtime_service.audit(workspace_id)
