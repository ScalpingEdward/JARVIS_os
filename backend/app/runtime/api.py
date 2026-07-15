from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    RuntimeHeartbeat,
    RuntimeRunCreate,
    RuntimeRunList,
    RuntimeRunRecord,
    RuntimeRunUpdate,
    RuntimeSummary,
    RuntimeWorkerCreate,
    RuntimeWorkerList,
    RuntimeWorkerRecord,
)
from .service import RuntimeError, agent_runtime_service

router = APIRouter(prefix="/v1/runtime", tags=["agent-runtime"])


@router.post("/workers", response_model=RuntimeWorkerRecord, status_code=status.HTTP_201_CREATED)
def register_runtime_worker(payload: RuntimeWorkerCreate) -> RuntimeWorkerRecord:
    try:
        return agent_runtime_service.register_worker(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/workers", response_model=RuntimeWorkerList)
def list_runtime_workers() -> RuntimeWorkerList:
    items = agent_runtime_service.list_workers()
    return RuntimeWorkerList(items=items, count=len(items))


@router.post("/workers/{worker_id}/heartbeat", response_model=RuntimeWorkerRecord)
def runtime_heartbeat(worker_id: UUID, payload: RuntimeHeartbeat) -> RuntimeWorkerRecord:
    try:
        return agent_runtime_service.heartbeat(worker_id, payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/discover", response_model=RuntimeWorkerList)
def discover_runtime_workers(stale_after_seconds: int = Query(default=120, ge=5, le=3600)) -> RuntimeWorkerList:
    items = agent_runtime_service.discover(stale_after_seconds)
    return RuntimeWorkerList(items=items, count=len(items))


@router.post("/runs", response_model=RuntimeRunRecord, status_code=status.HTTP_201_CREATED)
def create_runtime_run(payload: RuntimeRunCreate) -> RuntimeRunRecord:
    return agent_runtime_service.create_run(payload)


@router.get("/runs", response_model=RuntimeRunList)
def list_runtime_runs() -> RuntimeRunList:
    items = agent_runtime_service.list_runs()
    return RuntimeRunList(items=items, count=len(items))


@router.post("/runs/dispatch-next", response_model=RuntimeRunRecord)
def dispatch_next_runtime_run() -> RuntimeRunRecord:
    try:
        return agent_runtime_service.dispatch_next()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/runs/{run_id}", response_model=RuntimeRunRecord)
def update_runtime_run(run_id: UUID, payload: RuntimeRunUpdate) -> RuntimeRunRecord:
    try:
        return agent_runtime_service.update_run(run_id, payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/runs/{run_id}/retry", response_model=RuntimeRunRecord)
def retry_runtime_run(run_id: UUID) -> RuntimeRunRecord:
    try:
        return agent_runtime_service.retry(run_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/timeouts/expire", response_model=RuntimeRunList)
def expire_runtime_timeouts() -> RuntimeRunList:
    items = agent_runtime_service.expire_timeouts()
    return RuntimeRunList(items=items, count=len(items))


@router.get("/summary", response_model=RuntimeSummary)
def runtime_summary() -> RuntimeSummary:
    return agent_runtime_service.summary()
