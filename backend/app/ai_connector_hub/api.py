from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from .models import (
    AIConnectorHubStatus,
    ProviderMutation,
    ProviderRecord,
    ProviderRegister,
    RoutingDecision,
    RoutingRequest,
    UsageRecord,
    UsageRecordCreate,
)
from .service import ai_connector_hub_service


class HeartbeatPayload(BaseModel):
    healthy: bool = True
    message: str = Field(default="", max_length=500)


router = APIRouter(prefix="/v1/ai-connector-hub", tags=["ai-connector-hub"])


@router.get("/status", response_model=AIConnectorHubStatus)
def hub_status() -> AIConnectorHubStatus:
    return ai_connector_hub_service.status()


@router.post("/providers", response_model=ProviderRecord, status_code=status.HTTP_201_CREATED)
def register_provider(payload: ProviderRegister) -> ProviderRecord:
    try:
        return ai_connector_hub_service.register(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/providers", response_model=list[ProviderRecord])
def list_providers(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ProviderRecord]:
    return ai_connector_hub_service.list_providers(workspace_id)


@router.get("/providers/{provider_id}", response_model=ProviderRecord)
def get_provider(
    provider_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> ProviderRecord:
    provider = ai_connector_hub_service.get(provider_id, workspace_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.post("/providers/{provider_id}/activate", response_model=ProviderRecord)
def activate_provider(
    provider_id: UUID,
    payload: ProviderMutation,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> ProviderRecord:
    provider = ai_connector_hub_service.activate(provider_id, workspace_id, requester_id, payload)
    if provider is None:
        raise HTTPException(status_code=404, detail="Owned provider not found")
    return provider


@router.post("/providers/{provider_id}/disable", response_model=ProviderRecord)
def disable_provider(
    provider_id: UUID,
    payload: ProviderMutation,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> ProviderRecord:
    provider = ai_connector_hub_service.disable(provider_id, workspace_id, requester_id, payload)
    if provider is None:
        raise HTTPException(status_code=404, detail="Owned provider not found")
    return provider


@router.post("/providers/{provider_id}/heartbeat", response_model=ProviderRecord)
def provider_heartbeat(
    provider_id: UUID,
    payload: HeartbeatPayload,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> ProviderRecord:
    provider = ai_connector_hub_service.heartbeat(provider_id, workspace_id, payload.healthy, payload.message)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.post("/route", response_model=RoutingDecision, status_code=status.HTTP_201_CREATED)
def route_request(payload: RoutingRequest) -> RoutingDecision:
    return ai_connector_hub_service.route(payload)


@router.get("/routing-decisions", response_model=list[RoutingDecision])
def list_routing_decisions(
    workspace_id: str = Query(min_length=1, max_length=120),
) -> list[RoutingDecision]:
    return ai_connector_hub_service.list_decisions(workspace_id)


@router.post("/usage", response_model=UsageRecord, status_code=status.HTTP_201_CREATED)
def record_usage(payload: UsageRecordCreate) -> UsageRecord:
    record = ai_connector_hub_service.record_usage(payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Provider or model not found")
    return record


@router.get("/usage", response_model=list[UsageRecord])
def list_usage(workspace_id: str = Query(min_length=1, max_length=120)) -> list[UsageRecord]:
    return ai_connector_hub_service.list_usage(workspace_id)
