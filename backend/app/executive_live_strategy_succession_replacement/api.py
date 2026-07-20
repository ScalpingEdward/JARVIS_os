from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, SuccessionAssessment, SuccessionAssessmentCreate, SuccessionStatusResponse
from .service import executive_live_strategy_succession_replacement_service

router = APIRouter(tags=["executive-live-strategy-succession-replacement"])
BASE = "/v1/executive-live-strategy-succession-replacement"


@router.get(f"{BASE}/status", response_model=SuccessionStatusResponse)
def succession_status(workspace_id: str = Query(min_length=1, max_length=100)) -> SuccessionStatusResponse:
    return executive_live_strategy_succession_replacement_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=SuccessionAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: SuccessionAssessmentCreate) -> SuccessionAssessment:
    try:
        return executive_live_strategy_succession_replacement_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[SuccessionAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[SuccessionAssessment]:
    return executive_live_strategy_succession_replacement_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=SuccessionAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> SuccessionAssessment:
    item = executive_live_strategy_succession_replacement_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Succession assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def succession_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_live_strategy_succession_replacement_service.audit(workspace_id)
