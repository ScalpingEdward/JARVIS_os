from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import ApprovalRequest, AuditRecord, OrderIntent, OrderIntentCreate, OrderRoutingStatusResponse
from .service import executive_order_routing_service

router = APIRouter(tags=["executive-order-routing"])


@router.get("/v1/executive-order-routing/status", response_model=OrderRoutingStatusResponse)
def routing_status(workspace_id: str = Query(min_length=1, max_length=100)) -> OrderRoutingStatusResponse:
    return executive_order_routing_service.status(workspace_id)


@router.post("/v1/executive-order-routing/intents", response_model=OrderIntent, status_code=status.HTTP_201_CREATED)
def create_intent(payload: OrderIntentCreate) -> OrderIntent:
    try:
        return executive_order_routing_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-order-routing/intents", response_model=list[OrderIntent])
def list_intents(workspace_id: str = Query(min_length=1, max_length=100)) -> list[OrderIntent]:
    return executive_order_routing_service.list_intents(workspace_id)


@router.get("/v1/executive-order-routing/intents/{record_id}", response_model=OrderIntent)
def get_intent(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> OrderIntent:
    record = executive_order_routing_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Order intent not found")
    return record


@router.post("/v1/executive-order-routing/approve", response_model=OrderIntent)
def approve_intent(request: ApprovalRequest) -> OrderIntent:
    try:
        return executive_order_routing_service.approve(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-order-routing/audit", response_model=list[AuditRecord])
def routing_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_order_routing_service.audit_records(workspace_id)
