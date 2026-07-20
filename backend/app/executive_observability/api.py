from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, MetricsResponse, ObservabilityAssessment, ObservabilityAssessmentCreate, ObservabilityStatusResponse
from .service import executive_observability_service

router = APIRouter(tags=["executive-observability"])
BASE = "/v1/executive-observability"


@router.get(f"{BASE}/status", response_model=ObservabilityStatusResponse)
def observability_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ObservabilityStatusResponse:
    return executive_observability_service.status(workspace_id)


@router.post(f"{BASE}/traces", response_model=ObservabilityAssessment, status_code=status.HTTP_201_CREATED)
def create_trace(payload: ObservabilityAssessmentCreate) -> ObservabilityAssessment:
    try:
        return executive_observability_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/traces", response_model=list[ObservabilityAssessment])
def list_traces(workspace_id: str = Query(min_length=1, max_length=100)) -> list[ObservabilityAssessment]:
    return executive_observability_service.list_assessments(workspace_id)


@router.get(f"{BASE}/traces/{{assessment_id}}", response_model=ObservabilityAssessment)
def get_trace(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ObservabilityAssessment:
    item = executive_observability_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Observability trace not found")
    return item


@router.get(f"{BASE}/metrics", response_model=MetricsResponse)
def observability_metrics(workspace_id: str = Query(min_length=1, max_length=100)) -> MetricsResponse:
    return executive_observability_service.metrics(workspace_id)


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def observability_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_observability_service.audit(workspace_id)
