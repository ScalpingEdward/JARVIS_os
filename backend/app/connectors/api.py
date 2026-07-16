from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import (
    ConnectorAction,
    ConnectorAuditRecord,
    ConnectorCreate,
    ConnectorHealthUpdate,
    ConnectorListResponse,
    ConnectorPlatformStatus,
    ConnectorRecord,
)
from .service import connector_service

router = APIRouter(prefix="/v1/connectors", tags=["connectors"])


@router.get("/status", response_model=ConnectorPlatformStatus)
def connector_status() -> ConnectorPlatformStatus:
    return connector_service.status()


@router.post("", response_model=ConnectorRecord, status_code=status.HTTP_201_CREATED)
def create_connector(payload: ConnectorCreate) -> ConnectorRecord:
    return connector_service.create(payload)


@router.get("", response_model=ConnectorListResponse)
def list_connectors() -> ConnectorListResponse:
    items = connector_service.list_all()
    return ConnectorListResponse(items=items, count=len(items))


@router.get("/{connector_id}", response_model=ConnectorRecord)
def get_connector(connector_id: UUID) -> ConnectorRecord:
    record = connector_service.get(connector_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return record


@router.post("/{connector_id}/actions", response_model=ConnectorRecord)
def connector_action(connector_id: UUID, payload: ConnectorAction) -> ConnectorRecord:
    try:
        record = connector_service.transition(connector_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return record


@router.post("/{connector_id}/health", response_model=ConnectorRecord)
def connector_health(connector_id: UUID, payload: ConnectorHealthUpdate) -> ConnectorRecord:
    record = connector_service.update_health(connector_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return record


@router.get("/audit/all", response_model=list[ConnectorAuditRecord])
def connector_audit() -> list[ConnectorAuditRecord]:
    return connector_service.audit()
