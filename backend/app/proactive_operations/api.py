from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AlertList, AlertStatus, AlertStatusUpdate, OperationsAlert, OperationsEventCreate, OperationsStatus
from .service import proactive_operations_service


router = APIRouter(prefix="/v1/proactive-operations", tags=["proactive-operations"])


@router.get("/status", response_model=OperationsStatus)
def operations_status() -> OperationsStatus:
    return proactive_operations_service.status()


@router.post("/events", response_model=OperationsAlert, status_code=status.HTTP_202_ACCEPTED)
def ingest_event(payload: OperationsEventCreate) -> OperationsAlert:
    return proactive_operations_service.ingest(payload)


@router.get("/alerts", response_model=AlertList)
def list_alerts(alert_status: AlertStatus | None = Query(default=None, alias="status")) -> AlertList:
    items = proactive_operations_service.list_all(status=alert_status)
    return AlertList(items=items, count=len(items))


@router.get("/alerts/{alert_id}", response_model=OperationsAlert)
def get_alert(alert_id: UUID) -> OperationsAlert:
    item = proactive_operations_service.get(alert_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Operations alert not found")
    return item


@router.patch("/alerts/{alert_id}/status", response_model=OperationsAlert)
def update_alert_status(alert_id: UUID, payload: AlertStatusUpdate) -> OperationsAlert:
    item = proactive_operations_service.update_status(alert_id, payload.status)
    if item is None:
        raise HTTPException(status_code=404, detail="Operations alert not found")
    return item
