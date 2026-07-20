from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ConfigurationAssessment, ConfigurationAssessmentCreate, ConfigurationStatusResponse
from .service import executive_configuration_registry_service

router = APIRouter(tags=["executive-configuration-registry"])
BASE = "/v1/executive-configuration"


@router.get(f"{BASE}/status", response_model=ConfigurationStatusResponse)
def configuration_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ConfigurationStatusResponse:
    return executive_configuration_registry_service.status(workspace_id)


@router.post(f"{BASE}/configurations", response_model=ConfigurationAssessment, status_code=status.HTTP_201_CREATED)
def create_configuration(payload: ConfigurationAssessmentCreate) -> ConfigurationAssessment:
    try:
        return executive_configuration_registry_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/configurations", response_model=list[ConfigurationAssessment])
def list_configurations(workspace_id: str = Query(min_length=1, max_length=100)) -> list[ConfigurationAssessment]:
    return executive_configuration_registry_service.list_configurations(workspace_id)


@router.get(f"{BASE}/configurations/{{record_id}}", response_model=ConfigurationAssessment)
def get_configuration(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ConfigurationAssessment:
    item = executive_configuration_registry_service.get(record_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Configuration assessment not found")
    return item


@router.post(f"{BASE}/reload", response_model=ConfigurationAssessment)
def reload_configuration(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ConfigurationAssessment:
    item = executive_configuration_registry_service.get(record_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Configuration assessment not found")
    if item.state.value not in {"reload-required", "configuration-valid", "runtime-ready"}:
        raise HTTPException(status_code=409, detail="Configuration is not eligible for runtime reload")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def configuration_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_configuration_registry_service.audit(workspace_id)
