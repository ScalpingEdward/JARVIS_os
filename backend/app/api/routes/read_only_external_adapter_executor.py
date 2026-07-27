from fastapi import APIRouter, HTTPException, Query

from app.schemas.read_only_external_adapter_executor import (
    ReadOnlyExecutionAction,
    ReadOnlyExecutionCreate,
    ReadOnlyExecutionRecord,
    ReadOnlyExecutionResult,
)
from app.services.read_only_external_adapter_executor import read_only_external_adapter_executor_service as service

router = APIRouter(prefix="/v1/read-only-adapter-executor", tags=["read-only-adapter-executor"])


@router.get("/status")
def status() -> dict:
    return service.status()


@router.post("/records", response_model=ReadOnlyExecutionRecord)
def create_record(payload: ReadOnlyExecutionCreate) -> ReadOnlyExecutionRecord:
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ReadOnlyExecutionRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[ReadOnlyExecutionRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=ReadOnlyExecutionRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> ReadOnlyExecutionRecord:
    try:
        return service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ReadOnlyExecutionRecord)
def act(record_id: str, payload: ReadOnlyExecutionAction) -> ReadOnlyExecutionRecord:
    try:
        return service.act(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/records/{record_id}/result", response_model=ReadOnlyExecutionRecord)
def ingest_result(record_id: str, payload: ReadOnlyExecutionResult) -> ReadOnlyExecutionRecord:
    try:
        return service.ingest_result(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return service.audit(workspace_id)
