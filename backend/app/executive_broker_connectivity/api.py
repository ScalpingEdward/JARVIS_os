from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, BrokerConnectivityStatusResponse, BrokerSessionAssessment, BrokerSessionAssessmentCreate, ReconnectRequest
from .service import executive_broker_connectivity_service

router = APIRouter(prefix="/v1/executive-broker-connectivity", tags=["executive-broker-connectivity"])


@router.get("/status", response_model=BrokerConnectivityStatusResponse)
def connectivity_status(workspace_id: str = Query(min_length=1, max_length=100)) -> BrokerConnectivityStatusResponse:
    return executive_broker_connectivity_service.status(workspace_id)


@router.post("/sessions", response_model=BrokerSessionAssessment, status_code=status.HTTP_201_CREATED)
def create_session(payload: BrokerSessionAssessmentCreate) -> BrokerSessionAssessment:
    try:
        return executive_broker_connectivity_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/sessions", response_model=list[BrokerSessionAssessment])
def list_sessions(workspace_id: str = Query(min_length=1, max_length=100)) -> list[BrokerSessionAssessment]:
    return executive_broker_connectivity_service.list_sessions(workspace_id)


@router.get("/sessions/{record_id}", response_model=BrokerSessionAssessment)
def get_session(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> BrokerSessionAssessment:
    record = executive_broker_connectivity_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Broker session assessment not found")
    return record


@router.post("/reconnect", response_model=BrokerSessionAssessment)
def reconnect_session(payload: ReconnectRequest) -> BrokerSessionAssessment:
    try:
        return executive_broker_connectivity_service.reconnect(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditRecord])
def connectivity_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_broker_connectivity_service.audit_records(workspace_id)
