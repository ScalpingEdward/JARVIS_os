from fastapi import APIRouter, Header, HTTPException

from app.schemas.exchange_infrastructure_health import (
    InfrastructureHealthAction,
    InfrastructureHealthCreate,
    InfrastructureHealthRecord,
)
from app.services.exchange_infrastructure_health import ExchangeInfrastructureHealthService

router = APIRouter(prefix="/v1/exchange-infrastructure-health", tags=["exchange-infrastructure-health"])
service = ExchangeInfrastructureHealthService()


@router.get("/status")
def get_status() -> dict:
    return service.status()


@router.post("/records", response_model=InfrastructureHealthRecord)
def create_record(payload: InfrastructureHealthCreate) -> InfrastructureHealthRecord:
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[InfrastructureHealthRecord])
def list_records(x_workspace_id: str = Header(alias="X-Workspace-Id")) -> list[InfrastructureHealthRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=InfrastructureHealthRecord)
def get_record(record_id: str, x_workspace_id: str = Header(alias="X-Workspace-Id")) -> InfrastructureHealthRecord:
    try:
        return service.get(x_workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=InfrastructureHealthRecord)
def apply_action(
    record_id: str,
    payload: InfrastructureHealthAction,
    x_workspace_id: str = Header(alias="X-Workspace-Id"),
) -> InfrastructureHealthRecord:
    try:
        return service.act(x_workspace_id, record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/audit")
def get_audit(x_workspace_id: str = Header(alias="X-Workspace-Id")) -> list[dict]:
    return [event.__dict__ for event in service.audit(x_workspace_id)]
