from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, VisionRoutingAssessment, VisionRoutingAssessmentCreate, VisionRoutingStatusResponse
from .service import executive_vision_provider_routing_service

router = APIRouter(tags=["executive-vision-provider-routing"])
BASE = "/v1/executive-vision-provider-routing"


@router.get(f"{BASE}/status", response_model=VisionRoutingStatusResponse)
def routing_status(workspace_id: str = Query(min_length=1, max_length=100)) -> VisionRoutingStatusResponse:
    return executive_vision_provider_routing_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=VisionRoutingAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: VisionRoutingAssessmentCreate) -> VisionRoutingAssessment:
    try:
        return executive_vision_provider_routing_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[VisionRoutingAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[VisionRoutingAssessment]:
    return executive_vision_provider_routing_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=VisionRoutingAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> VisionRoutingAssessment:
    item = executive_vision_provider_routing_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Vision routing assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def routing_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_vision_provider_routing_service.audit(workspace_id)
