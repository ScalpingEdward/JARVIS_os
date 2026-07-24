from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.cybersecurity_privileged_access import (
    CyberAccessAction,
    CyberAccessGovernanceCreate,
    CyberAccessGovernanceRecord,
)
from app.services.cybersecurity_privileged_access import cybersecurity_privileged_access_service


router = APIRouter(prefix="/v1/cybersecurity-privileged-access", tags=["cybersecurity-privileged-access"])


@router.get("/status")
def status() -> dict:
    return cybersecurity_privileged_access_service.status()


@router.post("/records", response_model=CyberAccessGovernanceRecord)
def create_record(payload: CyberAccessGovernanceCreate) -> CyberAccessGovernanceRecord:
    try:
        return cybersecurity_privileged_access_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[CyberAccessGovernanceRecord])
def list_records(workspace_id: str = Query(min_length=2, max_length=128)) -> list[CyberAccessGovernanceRecord]:
    return cybersecurity_privileged_access_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=CyberAccessGovernanceRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=2, max_length=128)) -> CyberAccessGovernanceRecord:
    try:
        return cybersecurity_privileged_access_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=CyberAccessGovernanceRecord)
def act_on_record(
    record_id: str,
    payload: CyberAccessAction,
    workspace_id: str = Query(min_length=2, max_length=128),
) -> CyberAccessGovernanceRecord:
    try:
        return cybersecurity_privileged_access_service.act(
            workspace_id=workspace_id,
            record_id=record_id,
            action=payload.action,
            actor=payload.actor,
            operation_id=payload.operation_id,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=2, max_length=128)) -> list[dict]:
    return [entry.__dict__ for entry in cybersecurity_privileged_access_service.audit(workspace_id)]
