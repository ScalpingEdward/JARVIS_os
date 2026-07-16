from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    IntegrationHeartbeat,
    IntegrationHubStatus,
    LiveIntegration,
    LiveIntegrationCreate,
    LiveIntegrationList,
    NormalizedMarketEvent,
)
from .service import LiveIntegrationError, live_integration_service


router = APIRouter(prefix="/v1/live-integrations", tags=["live-integrations"])


@router.get("/status", response_model=IntegrationHubStatus)
def integration_status() -> IntegrationHubStatus:
    return live_integration_service.status()


@router.post("", response_model=LiveIntegration, status_code=status.HTTP_201_CREATED)
def create_integration(payload: LiveIntegrationCreate) -> LiveIntegration:
    try:
        return live_integration_service.create(payload)
    except LiveIntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=LiveIntegrationList)
def list_integrations() -> LiveIntegrationList:
    items = live_integration_service.list_all()
    return LiveIntegrationList(items=items, count=len(items))


@router.get("/{integration_id}", response_model=LiveIntegration)
def get_integration(integration_id: UUID) -> LiveIntegration:
    record = live_integration_service.get(integration_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Live integration not found")
    return record


@router.post("/{integration_id}/heartbeat", response_model=LiveIntegration)
def heartbeat(integration_id: UUID, payload: IntegrationHeartbeat) -> LiveIntegration:
    record = live_integration_service.heartbeat(integration_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Live integration not found")
    return record


@router.post("/events", response_model=NormalizedMarketEvent, status_code=status.HTTP_202_ACCEPTED)
def ingest_event(payload: NormalizedMarketEvent) -> NormalizedMarketEvent:
    return live_integration_service.ingest(payload)


@router.get("/events/recent", response_model=list[NormalizedMarketEvent])
def recent_events(symbol: str | None = Query(default=None, max_length=40), limit: int = Query(default=100, ge=1, le=500)) -> list[NormalizedMarketEvent]:
    return live_integration_service.events(symbol=symbol, limit=limit)
