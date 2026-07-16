from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    BrokerAccount,
    BrokerAccountCreate,
    BrokerConnection,
    BrokerConnectionCreate,
    BrokerFleetStatus,
    ConnectorState,
    SymbolResolution,
)
from .service import multi_broker_service


router = APIRouter(prefix="/v1/multi-broker", tags=["multi-broker"])


@router.get("/status", response_model=BrokerFleetStatus)
def fleet_status() -> BrokerFleetStatus:
    return multi_broker_service.fleet_status()


@router.post("/brokers", response_model=BrokerConnection, status_code=status.HTTP_201_CREATED)
def register_broker(payload: BrokerConnectionCreate) -> BrokerConnection:
    try:
        return multi_broker_service.register_broker(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/brokers", response_model=list[BrokerConnection])
def list_brokers() -> list[BrokerConnection]:
    return multi_broker_service.list_brokers()


@router.get("/brokers/{broker_id}", response_model=BrokerConnection)
def get_broker(broker_id: UUID) -> BrokerConnection:
    broker = multi_broker_service.get_broker(broker_id)
    if broker is None:
        raise HTTPException(status_code=404, detail="Broker connection not found")
    return broker


@router.post("/brokers/{broker_id}/heartbeat", response_model=BrokerConnection)
def broker_heartbeat(
    broker_id: UUID,
    state: ConnectorState,
    latency_ms: int | None = Query(default=None, ge=0),
) -> BrokerConnection:
    broker = multi_broker_service.heartbeat(broker_id, state, latency_ms)
    if broker is None:
        raise HTTPException(status_code=404, detail="Broker connection not found")
    return broker


@router.post("/accounts", response_model=BrokerAccount, status_code=status.HTTP_201_CREATED)
def add_account(payload: BrokerAccountCreate) -> BrokerAccount:
    try:
        return multi_broker_service.add_account(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/accounts", response_model=list[BrokerAccount])
def list_accounts(broker_id: UUID | None = None) -> list[BrokerAccount]:
    return multi_broker_service.list_accounts(broker_id)


@router.get("/accounts/{account_id}", response_model=BrokerAccount)
def get_account(account_id: UUID) -> BrokerAccount:
    account = multi_broker_service.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Broker account not found")
    return account


@router.get("/brokers/{broker_id}/symbols/{canonical_symbol}", response_model=SymbolResolution)
def resolve_symbol(broker_id: UUID, canonical_symbol: str) -> SymbolResolution:
    resolution = multi_broker_service.resolve_symbol(broker_id, canonical_symbol)
    if resolution is None:
        raise HTTPException(status_code=404, detail="Broker connection not found")
    return resolution
