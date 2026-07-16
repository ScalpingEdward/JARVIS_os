from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import ComponentConfig, ComponentConfigCreate, ComponentConfigList, ControlPlaneStatus, ReadinessCheck
from .service import configuration_control_service


router = APIRouter(prefix="/v1/config-control", tags=["config-control"])


@router.get("/status", response_model=ControlPlaneStatus)
def control_plane_status() -> ControlPlaneStatus:
    return configuration_control_service.status()


@router.post("/components", response_model=ComponentConfig, status_code=status.HTTP_201_CREATED)
def create_component(payload: ComponentConfigCreate) -> ComponentConfig:
    return configuration_control_service.create(payload)


@router.get("/components", response_model=ComponentConfigList)
def list_components() -> ComponentConfigList:
    items = configuration_control_service.list_all()
    return ComponentConfigList(items=items, count=len(items))


@router.get("/components/{component_id}", response_model=ComponentConfig)
def get_component(component_id: UUID) -> ComponentConfig:
    record = configuration_control_service.get(component_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Configuration component not found")
    return record


@router.post("/components/{component_id}/validate", response_model=ComponentConfig)
def validate_component(component_id: UUID) -> ComponentConfig:
    if configuration_control_service.get(component_id) is None:
        raise HTTPException(status_code=404, detail="Configuration component not found")
    return configuration_control_service.validate(component_id)


@router.post("/validate-all", response_model=list[ReadinessCheck])
def validate_all_components() -> list[ReadinessCheck]:
    return configuration_control_service.validate_all()
