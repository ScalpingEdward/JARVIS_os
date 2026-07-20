from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ProbationAssessment, ProbationAssessmentCreate, ProbationStatusResponse
from .service import executive_live_strategy_probation_canary_expansion_service

router = APIRouter(tags=["executive-live-strategy-probation-canary-expansion"])
BASE = "/v1/executive-live-strategy-probation-canary-expansion"


@router.get(f"{BASE}/status", response_model=ProbationStatusResponse)
def probation_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ProbationStatusResponse:
    return executive_live_strategy_probation_canary_expansion_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=ProbationAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: ProbationAssessmentCreate) -> ProbationAssessment:
    try:
        return executive_live_strategy_probation_canary_expansion_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[ProbationAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[ProbationAssessment]:
    return executive_live_strategy_probation_canary_expansion_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=ProbationAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ProbationAssessment:
    item = executive_live_strategy_probation_canary_expansion_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Probation assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def probation_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_live_strategy_probation_canary_expansion_service.audit(workspace_id)
