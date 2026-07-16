from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import OrderflowSnapshot, OrderflowSnapshotCreate, OrderflowSnapshotList, OrderflowStatus
from .service import orderflow_service

router = APIRouter(prefix="/v1/orderflow", tags=["orderflow"])


@router.get("/status", response_model=OrderflowStatus)
def orderflow_status() -> OrderflowStatus:
    return orderflow_service.status()


@router.post("/snapshots", response_model=OrderflowSnapshot, status_code=status.HTTP_201_CREATED)
def create_snapshot(payload: OrderflowSnapshotCreate) -> OrderflowSnapshot:
    return orderflow_service.create(payload)


@router.get("/snapshots", response_model=OrderflowSnapshotList)
def list_snapshots(symbol: str | None = Query(default=None, max_length=30)) -> OrderflowSnapshotList:
    items = orderflow_service.list_all(symbol=symbol)
    return OrderflowSnapshotList(items=items, count=len(items))


@router.get("/snapshots/{snapshot_id}", response_model=OrderflowSnapshot)
def get_snapshot(snapshot_id: UUID) -> OrderflowSnapshot:
    snapshot = orderflow_service.get(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Orderflow snapshot not found")
    return snapshot


@router.get("/latest/{symbol}", response_model=OrderflowSnapshot)
def latest_snapshot(symbol: str) -> OrderflowSnapshot:
    snapshot = orderflow_service.latest(symbol)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No orderflow data for symbol")
    return snapshot
