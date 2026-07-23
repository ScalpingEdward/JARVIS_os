from fastapi import APIRouter, Header, HTTPException, Query, status

from app.schemas.multi_broker_intelligence import (
    MultiBrokerAction,
    MultiBrokerCreate,
    MultiBrokerRecord,
)
from app.services.multi_broker_intelligence import (
    MultiBrokerConflictError,
    MultiBrokerNotFoundError,
    MultiBrokerPolicyError,
    multi_broker_intelligence_service,
)

router = APIRouter(prefix="/v1/multi-broker-intelligence", tags=["multi-broker-intelligence"])


@router.get("/status")
def status_endpoint() -> dict:
    return multi_broker_intelligence_service.status()


@router.post("/records", response_model=MultiBrokerRecord, status_code=status.HTTP_201_CREATED)
def create_record(payload: MultiBrokerCreate) -> MultiBrokerRecord:
    try:
        return multi_broker_intelligence_service.create(payload)
    except MultiBrokerConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/records", response_model=list[MultiBrokerRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[MultiBrokerRecord]:
    return multi_broker_intelligence_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=MultiBrokerRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> MultiBrokerRecord:
    try:
        return multi_broker_intelligence_service.get(workspace_id, record_id)
    except MultiBrokerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=MultiBrokerRecord)
def apply_action(
    record_id: str,
    payload: MultiBrokerAction,
    workspace_id: str = Header(alias="X-Workspace-ID", min_length=1),
) -> MultiBrokerRecord:
    try:
        return multi_broker_intelligence_service.action(workspace_id, record_id, payload)
    except MultiBrokerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MultiBrokerConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except MultiBrokerPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/audit")
def audit_endpoint(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return multi_broker_intelligence_service.audit(workspace_id)
