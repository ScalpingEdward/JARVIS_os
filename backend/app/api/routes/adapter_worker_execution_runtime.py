from fastapi import APIRouter, HTTPException, Query

from app.schemas.adapter_worker_execution_runtime import (
    AdapterWorkerAction,
    AdapterWorkerExecutionCreate,
    AdapterWorkerHeartbeat,
    AdapterWorkerLeaseRequest,
    AdapterWorkerRecord,
    AdapterWorkerResult,
)
from app.services.adapter_worker_execution_runtime import adapter_worker_execution_runtime_service as service

router = APIRouter(prefix="/v1/adapter-worker-runtime", tags=["adapter-worker-runtime"])


@router.get("/status")
def status() -> dict:
    return service.status()


@router.post("/records", response_model=AdapterWorkerRecord)
def create_record(payload: AdapterWorkerExecutionCreate) -> AdapterWorkerRecord:
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AdapterWorkerRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AdapterWorkerRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AdapterWorkerRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AdapterWorkerRecord:
    try:
        return service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/lease", response_model=AdapterWorkerRecord)
def lease(record_id: str, payload: AdapterWorkerLeaseRequest) -> AdapterWorkerRecord:
    try:
        return service.lease(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/records/{record_id}/heartbeat", response_model=AdapterWorkerRecord)
def heartbeat(record_id: str, payload: AdapterWorkerHeartbeat) -> AdapterWorkerRecord:
    try:
        return service.heartbeat(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/records/{record_id}/result", response_model=AdapterWorkerRecord)
def result(record_id: str, payload: AdapterWorkerResult) -> AdapterWorkerRecord:
    try:
        return service.ingest_result(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AdapterWorkerRecord)
def act(record_id: str, payload: AdapterWorkerAction) -> AdapterWorkerRecord:
    try:
        if payload.action == "cancel":
            return service.cancel(payload.workspace_id, record_id, payload.actor, payload.operation_id, payload.reason)
        if payload.action == "expire-lease":
            return service.expire_stale_lease(payload.workspace_id, record_id, payload.actor, payload.operation_id)
        raise ValueError("unsupported action")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return service.audit(workspace_id)
