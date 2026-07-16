from uuid import UUID

from fastapi import APIRouter, HTTPException

from .models import ConnectorImplementationStatus, ConnectorInvocation, ConnectorInvocationResult
from .service import ConnectorRuntimeError, connector_runtime_service

router = APIRouter(prefix="/v1/connector-runtime", tags=["connector-runtime"])


@router.get("/status", response_model=ConnectorImplementationStatus)
def runtime_status() -> ConnectorImplementationStatus:
    return connector_runtime_service.status()


@router.post("/{connector_id}/invoke", response_model=ConnectorInvocationResult)
def invoke_connector(connector_id: UUID, payload: ConnectorInvocation) -> ConnectorInvocationResult:
    try:
        return connector_runtime_service.invoke(connector_id, payload)
    except ConnectorRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/history", response_model=list[ConnectorInvocationResult])
def invocation_history() -> list[ConnectorInvocationResult]:
    return connector_runtime_service.history()


@router.get("/{connector_id}/history", response_model=list[ConnectorInvocationResult])
def connector_history(connector_id: UUID) -> list[ConnectorInvocationResult]:
    return connector_runtime_service.history(connector_id)
