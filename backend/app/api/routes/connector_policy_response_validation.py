from fastapi import APIRouter, HTTPException, Query

from app.schemas.connector_policy_response_validation import (
    ConnectorPolicyAction,
    ConnectorPolicyCreate,
    ConnectorPolicyRecord,
    ConnectorResponseAcceptAction,
    ConnectorResponseEnvelope,
    ConnectorResponseRecord,
)
from app.services.connector_policy_response_validation import connector_policy_response_validation_service as service

router = APIRouter(prefix="/v1/connector-response-policy", tags=["connector-response-policy"])


@router.get("/status")
def status() -> dict:
    return service.status()


@router.post("/policies", response_model=ConnectorPolicyRecord)
def create_policy(payload: ConnectorPolicyCreate) -> ConnectorPolicyRecord:
    try:
        return service.create_policy(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/policies", response_model=list[ConnectorPolicyRecord])
def list_policies(workspace_id: str = Query(min_length=1)) -> list[ConnectorPolicyRecord]:
    return service.list_policies(workspace_id)


@router.get("/policies/{record_id}", response_model=ConnectorPolicyRecord)
def get_policy(record_id: str, workspace_id: str = Query(min_length=1)) -> ConnectorPolicyRecord:
    try:
        return service.get_policy(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/policies/{record_id}/actions", response_model=ConnectorPolicyRecord)
def act_policy(record_id: str, payload: ConnectorPolicyAction) -> ConnectorPolicyRecord:
    try:
        return service.act_policy(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/responses", response_model=ConnectorResponseRecord)
def ingest_response(payload: ConnectorResponseEnvelope) -> ConnectorResponseRecord:
    try:
        return service.ingest_response(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/responses", response_model=list[ConnectorResponseRecord])
def list_responses(workspace_id: str = Query(min_length=1)) -> list[ConnectorResponseRecord]:
    return service.list_responses(workspace_id)


@router.get("/responses/{response_id}", response_model=ConnectorResponseRecord)
def get_response(response_id: str, workspace_id: str = Query(min_length=1)) -> ConnectorResponseRecord:
    try:
        return service.get_response(workspace_id, response_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/responses/{response_id}/accept", response_model=ConnectorResponseRecord)
def accept_response(response_id: str, payload: ConnectorResponseAcceptAction) -> ConnectorResponseRecord:
    try:
        return service.accept_response(response_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return service.audit(workspace_id)
