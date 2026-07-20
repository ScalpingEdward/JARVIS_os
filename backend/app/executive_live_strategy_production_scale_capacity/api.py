from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ProductionScaleAssessment, ProductionScaleAssessmentCreate, ProductionScaleStatusResponse
from .service import executive_live_strategy_production_scale_capacity_service

router = APIRouter(tags=["executive-live-strategy-production-scale-capacity"])
BASE = "/v1/executive-live-strategy-production-scale-capacity"


@router.get(f"{BASE}/status", response_model=ProductionScaleStatusResponse)
def production_scale_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ProductionScaleStatusResponse:
    return executive_live_strategy_production_scale_capacity_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=ProductionScaleAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: ProductionScaleAssessmentCreate) -> ProductionScaleAssessment:
    try:
        return executive_live_strategy_production_scale_capacity_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[ProductionScaleAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[ProductionScaleAssessment]:
    return executive_live_strategy_production_scale_capacity_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=ProductionScaleAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ProductionScaleAssessment:
    item = executive_live_strategy_production_scale_capacity_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Production scale assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def production_scale_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_live_strategy_production_scale_capacity_service.audit(workspace_id)
