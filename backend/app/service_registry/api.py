from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    DependencyCreate, DependencyRecord, GraphRecord, HealthUpdate, ImpactRecord,
    ImpactRequest, Mutation, RegistryStatus, ServiceCreate, ServiceRecord,
    ServiceState,
)
from .service import service_registry_service as service

router = APIRouter(prefix="/v1/service-registry", tags=["service-registry"])


@router.get("/status", response_model=RegistryStatus)
def get_status() -> RegistryStatus:
    return service.status()


@router.post("/services", response_model=ServiceRecord, status_code=status.HTTP_201_CREATED)
def create_service(payload: ServiceCreate) -> ServiceRecord:
    try:
        return service.create_service(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/services", response_model=list[ServiceRecord])
def list_services(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ServiceRecord]:
    return service.list_services(workspace_id)


@router.get("/services/{service_id}", response_model=ServiceRecord)
def get_service(service_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> ServiceRecord:
    item = service.get_service(service_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Service not found")
    return item


def _set_service(service_id: UUID, workspace_id: str, payload: Mutation, state: ServiceState) -> ServiceRecord:
    item = service.set_service_state(service_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned service not found")
    return item


@router.post("/services/{service_id}/activate", response_model=ServiceRecord)
def activate_service(service_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ServiceRecord:
    return _set_service(service_id, workspace_id, payload, ServiceState.ACTIVE)


@router.post("/services/{service_id}/suspend", response_model=ServiceRecord)
def suspend_service(service_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ServiceRecord:
    return _set_service(service_id, workspace_id, payload, ServiceState.SUSPENDED)


@router.post("/services/{service_id}/retire", response_model=ServiceRecord)
def retire_service(service_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ServiceRecord:
    return _set_service(service_id, workspace_id, payload, ServiceState.RETIRED)


@router.post("/services/{service_id}/health", response_model=ServiceRecord)
def update_health(service_id: UUID, payload: HealthUpdate, workspace_id: str = Query(min_length=1, max_length=120)) -> ServiceRecord:
    item = service.update_health(service_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned service not found")
    return item


@router.post("/dependencies", response_model=DependencyRecord, status_code=status.HTTP_201_CREATED)
def create_dependency(payload: DependencyCreate) -> DependencyRecord:
    try:
        return service.create_dependency(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/dependencies", response_model=list[DependencyRecord])
def list_dependencies(workspace_id: str = Query(min_length=1, max_length=120)) -> list[DependencyRecord]:
    return service.list_dependencies(workspace_id)


@router.get("/graph", response_model=GraphRecord)
def get_graph(workspace_id: str = Query(min_length=1, max_length=120)) -> GraphRecord:
    return service.graph(workspace_id)


@router.post("/impact-analysis", response_model=ImpactRecord)
def analyze_impact(payload: ImpactRequest) -> ImpactRecord:
    try:
        return service.impact(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/capabilities")
def list_capabilities(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_capabilities(workspace_id)


@router.get("/audit")
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
