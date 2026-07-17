from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ApprovalRequest,
    AuditRecord,
    CommandCreate,
    CommandRecord,
    HealthUpdate,
    IntegrationEventCreate,
    IntegrationEventRecord,
    IntegrationHubStatus,
    ModuleRecord,
    ModuleRegistrationCreate,
    ReplayRequest,
    SubscriptionCreate,
    SubscriptionRecord,
)
from .service import integration_hub_service


router = APIRouter(prefix="/v1/integration-hub", tags=["integration-hub"])


@router.get("/status", response_model=IntegrationHubStatus)
def hub_status() -> IntegrationHubStatus:
    return integration_hub_service.status()


@router.post("/modules/register", response_model=ModuleRecord, status_code=status.HTTP_201_CREATED)
def register_module(payload: ModuleRegistrationCreate) -> ModuleRecord:
    try:
        return integration_hub_service.create_module(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/modules", response_model=list[ModuleRecord])
def list_modules(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ModuleRecord]:
    return integration_hub_service.list_modules(workspace_id)


@router.get("/modules/{module_id}", response_model=ModuleRecord)
def get_module(module_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> ModuleRecord:
    item = integration_hub_service.get_module(module_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Integration module not found")
    return item


@router.post("/modules/{module_id}/health", response_model=ModuleRecord)
def update_module_health(module_id: UUID, payload: HealthUpdate, workspace_id: str = Query(min_length=1, max_length=120)) -> ModuleRecord:
    item = integration_hub_service.update_health(module_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned integration module not found")
    return item


@router.post("/events", response_model=IntegrationEventRecord, status_code=status.HTTP_201_CREATED)
def publish_event(payload: IntegrationEventCreate) -> IntegrationEventRecord:
    try:
        return integration_hub_service.publish_event(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/events", response_model=list[IntegrationEventRecord])
def list_events(workspace_id: str = Query(min_length=1, max_length=120), event_type: str | None = None) -> list[IntegrationEventRecord]:
    return integration_hub_service.list_events(workspace_id, event_type)


@router.post("/events/replay", response_model=list[IntegrationEventRecord])
def replay_events(payload: ReplayRequest) -> list[IntegrationEventRecord]:
    return integration_hub_service.replay_events(payload)


@router.post("/subscriptions", response_model=SubscriptionRecord, status_code=status.HTTP_201_CREATED)
def create_subscription(payload: SubscriptionCreate) -> SubscriptionRecord:
    try:
        return integration_hub_service.create_subscription(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/subscriptions", response_model=list[SubscriptionRecord])
def list_subscriptions(workspace_id: str = Query(min_length=1, max_length=120)) -> list[SubscriptionRecord]:
    return integration_hub_service.list_subscriptions(workspace_id)


@router.post("/commands", response_model=CommandRecord, status_code=status.HTTP_201_CREATED)
def create_command(payload: CommandCreate) -> CommandRecord:
    try:
        return integration_hub_service.create_command(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/commands", response_model=list[CommandRecord])
def list_commands(workspace_id: str = Query(min_length=1, max_length=120)) -> list[CommandRecord]:
    return integration_hub_service.list_commands(workspace_id)


@router.post("/commands/{command_id}/approval", response_model=CommandRecord)
def approve_command(command_id: UUID, payload: ApprovalRequest, workspace_id: str = Query(min_length=1, max_length=120)) -> CommandRecord:
    item = integration_hub_service.approve_command(command_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Approvable owned command not found")
    return item


@router.get("/health", response_model=list[ModuleRecord])
def health_report(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ModuleRecord]:
    return integration_hub_service.list_modules(workspace_id)


@router.get("/audit", response_model=list[AuditRecord])
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return integration_hub_service.list_audit(workspace_id)
