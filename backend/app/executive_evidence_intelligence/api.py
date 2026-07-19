from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    EvidenceAssessment,
    EvidenceAssessmentListResponse,
    EvidenceComparison,
    EvidenceComparisonCreate,
    EvidenceComparisonListResponse,
    EvidenceObservation,
    EvidenceObservationCreate,
    EvidenceObservationListResponse,
    EvidenceQuery,
    EvidenceStatusResponse,
)
from .service import executive_evidence_intelligence_service

router = APIRouter(tags=["executive-evidence-intelligence"])


@router.get("/v1/executive-evidence-intelligence/status", response_model=EvidenceStatusResponse)
def evidence_status(workspace_id: str = Query(min_length=1, max_length=100)) -> EvidenceStatusResponse:
    return executive_evidence_intelligence_service.status(workspace_id)


@router.post(
    "/v1/executive-evidence-intelligence/observations",
    response_model=EvidenceObservation,
    status_code=status.HTTP_201_CREATED,
)
def record_observation(payload: EvidenceObservationCreate) -> EvidenceObservation:
    try:
        return executive_evidence_intelligence_service.record_observation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/v1/executive-evidence-intelligence/observations",
    response_model=EvidenceObservationListResponse,
)
def list_observations(workspace_id: str = Query(min_length=1, max_length=100)) -> EvidenceObservationListResponse:
    items = executive_evidence_intelligence_service.list_observations(workspace_id)
    return EvidenceObservationListResponse(items=items, count=len(items))


@router.get(
    "/v1/executive-evidence-intelligence/observations/{observation_id}",
    response_model=EvidenceObservation,
)
def get_observation(
    observation_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> EvidenceObservation:
    item = executive_evidence_intelligence_service.get_observation(observation_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Evidence observation not found")
    return item


@router.post(
    "/v1/executive-evidence-intelligence/assessments",
    response_model=EvidenceAssessment,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(
    payload: EvidenceQuery,
    actor_id: str = Query(min_length=1, max_length=100),
) -> EvidenceAssessment:
    return executive_evidence_intelligence_service.assess(payload, actor_id)


@router.get(
    "/v1/executive-evidence-intelligence/assessments",
    response_model=EvidenceAssessmentListResponse,
)
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> EvidenceAssessmentListResponse:
    items = executive_evidence_intelligence_service.list_assessments(workspace_id)
    return EvidenceAssessmentListResponse(items=items, count=len(items))


@router.post(
    "/v1/executive-evidence-intelligence/comparisons",
    response_model=EvidenceComparison,
    status_code=status.HTTP_201_CREATED,
)
def compare_evidence(payload: EvidenceComparisonCreate) -> EvidenceComparison:
    return executive_evidence_intelligence_service.compare(payload)


@router.get(
    "/v1/executive-evidence-intelligence/comparisons",
    response_model=EvidenceComparisonListResponse,
)
def list_comparisons(workspace_id: str = Query(min_length=1, max_length=100)) -> EvidenceComparisonListResponse:
    items = executive_evidence_intelligence_service.list_comparisons(workspace_id)
    return EvidenceComparisonListResponse(items=items, count=len(items))


@router.get("/v1/executive-evidence-intelligence/audit", response_model=list[AuditRecord])
def evidence_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_evidence_intelligence_service.audit_records(workspace_id)
