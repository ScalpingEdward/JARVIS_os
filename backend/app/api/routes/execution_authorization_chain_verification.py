from fastapi import APIRouter, HTTPException, Query

from app.schemas.execution_authorization_chain_verification import (
    AuthorizationChainAction,
    AuthorizationChainCreate,
    AuthorizationChainRecord,
)
from app.services.execution_authorization_chain_verification import (
    execution_authorization_chain_verification_service as service,
)

router = APIRouter(
    prefix="/v1/execution-authorization-chain",
    tags=["execution-authorization-chain"],
)


@router.get("/status")
def status():
    return service.status()


@router.post("/records", response_model=AuthorizationChainRecord)
def create_record(payload: AuthorizationChainCreate):
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AuthorizationChainRecord])
def list_records(workspace_id: str = Query(min_length=1)):
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AuthorizationChainRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)):
    try:
        return service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AuthorizationChainRecord)
def act(record_id: str, payload: AuthorizationChainAction):
    try:
        return service.act(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)):
    return service.audit(workspace_id)
