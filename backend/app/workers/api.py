from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import (
    DispatchListResponse,
    DispatchRecord,
    DispatchRequest,
    WorkerCallback,
    WorkerEndpointCreate,
    WorkerEndpointRecord,
    WorkerListResponse,
)
from .service import WorkerGatewayError, worker_gateway_service

router = APIRouter(prefix="/v1/workers", tags=["workers"])


@router.post("", response_model=WorkerEndpointRecord, status_code=status.HTTP_201_CREATED)
def register_worker(payload: WorkerEndpointCreate) -> WorkerEndpointRecord:
    try:
        return worker_gateway_service.register(payload)
    except WorkerGatewayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=WorkerListResponse)
def list_workers() -> WorkerListResponse:
    items = worker_gateway_service.list_workers()
    return WorkerListResponse(items=items, count=len(items))


@router.post("/dispatch", response_model=DispatchRecord)
def dispatch_task(payload: DispatchRequest) -> DispatchRecord:
    try:
        return worker_gateway_service.dispatch(payload.task_id, payload.worker_id)
    except WorkerGatewayError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/dispatches", response_model=DispatchListResponse)
def list_dispatches() -> DispatchListResponse:
    items = worker_gateway_service.list_dispatches()
    return DispatchListResponse(items=items, count=len(items))


@router.post("/dispatches/{dispatch_id}/callback", response_model=DispatchRecord)
def worker_callback(dispatch_id: UUID, payload: WorkerCallback) -> DispatchRecord:
    record = worker_gateway_service.callback(dispatch_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Dispatch not found")
    return record
