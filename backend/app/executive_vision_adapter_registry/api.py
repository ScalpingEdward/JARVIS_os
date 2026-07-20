from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AdapterRegistryAssessment, AdapterRegistryAssessmentCreate, AdapterRegistryStatusResponse, AuditRecord
from .service import executive_vision_adapter_registry_service

router = APIRouter(tags=["executive-vision-adapter-registry"])
BASE = "/v1/executive-vision-adapter-registry"


@router.get(f"{BASE}/status", response_model=AdapterRegistryStatusResponse)
def registry_status(workspace_id: str = Query(min_length=1, max_length=100)) -> AdapterRegistryStatusResponse:
    return executive_vision_adapter_registry_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=AdapterRegistryAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: AdapterRegistryAssessmentCreate) -> AdapterRegistryAssessment:
    try:
        return executive_vision_adapter_registry_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[AdapterRegistryAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AdapterRegistryAssessment]:
    return executive_vision_adapter_registry_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=AdapterRegistryAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> AdapterRegistryAssessment:
    item = executive_vision_adapter_registry_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Vision adapter registry assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def registry_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_vision_adapter_registry_service.audit(workspace_id)
