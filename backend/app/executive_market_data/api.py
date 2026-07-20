from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, MarketDataStatusResponse, MarketDataSubscription, MarketDataSubscriptionCreate, RecoverStreamRequest
from .service import executive_market_data_service

router = APIRouter(tags=["executive-market-data"])


@router.get("/v1/executive-market-data/status", response_model=MarketDataStatusResponse)
def market_data_status(workspace_id: str = Query(min_length=1, max_length=100)) -> MarketDataStatusResponse:
    return executive_market_data_service.status(workspace_id)


@router.post("/v1/executive-market-data/subscriptions", response_model=MarketDataSubscription, status_code=status.HTTP_201_CREATED)
def create_subscription(payload: MarketDataSubscriptionCreate) -> MarketDataSubscription:
    try:
        return executive_market_data_service.subscribe(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-market-data/subscriptions", response_model=list[MarketDataSubscription])
def list_subscriptions(workspace_id: str = Query(min_length=1, max_length=100)) -> list[MarketDataSubscription]:
    return executive_market_data_service.list_subscriptions(workspace_id)


@router.post("/v1/executive-market-data/recover", response_model=MarketDataSubscription)
def recover_stream(request: RecoverStreamRequest) -> MarketDataSubscription:
    try:
        return executive_market_data_service.recover(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-market-data/audit", response_model=list[AuditRecord])
def market_data_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_market_data_service.audit_records(workspace_id)


@router.get("/v1/executive-market-data/subscriptions/{record_id}", response_model=MarketDataSubscription)
def get_subscription(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> MarketDataSubscription:
    record = executive_market_data_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Market-data subscription not found")
    return record
