from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AlertCreate, AlertRecord, AuditRecord, ControlSwitchCreate, ControlSwitchRecord,
    IncidentCreate, IncidentRecord, IncidentState, MetricCreate, MetricRecord,
    ObservabilityStatus, OperatorMutation, SLOCreate, SLORecord, SwitchState,
    TraceCreate, TraceRecord,
)
from .service import observability_control_service

router = APIRouter(prefix="/v1/observability-control", tags=["observability-control"])


@router.get("/status", response_model=ObservabilityStatus)
def get_status() -> ObservabilityStatus:
    return observability_control_service.status()


@router.post("/metrics", response_model=MetricRecord, status_code=status.HTTP_201_CREATED)
def add_metric(payload: MetricCreate) -> MetricRecord:
    return observability_control_service.add_metric(payload)


@router.get("/metrics", response_model=list[MetricRecord])
def list_metrics(workspace_id: str = Query(min_length=1, max_length=120), source_module: str | None = None) -> list[MetricRecord]:
    return observability_control_service.list_metrics(workspace_id, source_module)


@router.post("/traces", response_model=TraceRecord, status_code=status.HTTP_201_CREATED)
def add_trace(payload: TraceCreate) -> TraceRecord:
    try:
        return observability_control_service.add_trace(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/traces", response_model=list[TraceRecord])
def list_traces(workspace_id: str = Query(min_length=1, max_length=120), trace_id: str | None = None) -> list[TraceRecord]:
    return observability_control_service.list_traces(workspace_id, trace_id)


@router.post("/alerts", response_model=AlertRecord, status_code=status.HTTP_201_CREATED)
def create_alert(payload: AlertCreate) -> AlertRecord:
    return observability_control_service.create_alert(payload)


@router.get("/alerts", response_model=list[AlertRecord])
def list_alerts(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AlertRecord]:
    return observability_control_service.list_alerts(workspace_id)


@router.post("/incidents", response_model=IncidentRecord, status_code=status.HTTP_201_CREATED)
def create_incident(payload: IncidentCreate) -> IncidentRecord:
    return observability_control_service.create_incident(payload)


@router.get("/incidents", response_model=list[IncidentRecord])
def list_incidents(workspace_id: str = Query(min_length=1, max_length=120)) -> list[IncidentRecord]:
    return observability_control_service.list_incidents(workspace_id)


def _mutate_incident(incident_id: UUID, workspace_id: str, payload: OperatorMutation, state: IncidentState) -> IncidentRecord:
    item = observability_control_service.mutate_incident(incident_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned incident not found")
    return item


@router.post("/incidents/{incident_id}/acknowledge", response_model=IncidentRecord)
def acknowledge_incident(incident_id: UUID, payload: OperatorMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> IncidentRecord:
    return _mutate_incident(incident_id, workspace_id, payload, IncidentState.ACKNOWLEDGED)


@router.post("/incidents/{incident_id}/resolve", response_model=IncidentRecord)
def resolve_incident(incident_id: UUID, payload: OperatorMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> IncidentRecord:
    return _mutate_incident(incident_id, workspace_id, payload, IncidentState.RESOLVED)


@router.post("/slos", response_model=SLORecord, status_code=status.HTTP_201_CREATED)
def create_slo(payload: SLOCreate) -> SLORecord:
    try:
        return observability_control_service.create_slo(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/slos", response_model=list[SLORecord])
def list_slos(workspace_id: str = Query(min_length=1, max_length=120)) -> list[SLORecord]:
    return observability_control_service.list_slos(workspace_id)


@router.post("/switches", response_model=ControlSwitchRecord, status_code=status.HTTP_201_CREATED)
def create_switch(payload: ControlSwitchCreate) -> ControlSwitchRecord:
    return observability_control_service.create_switch(payload)


@router.get("/switches", response_model=list[ControlSwitchRecord])
def list_switches(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ControlSwitchRecord]:
    return observability_control_service.list_switches(workspace_id)


def _set_switch(switch_id: UUID, workspace_id: str, payload: OperatorMutation, state: SwitchState) -> ControlSwitchRecord:
    item = observability_control_service.set_switch(switch_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned control switch not found")
    return item


@router.post("/switches/{switch_id}/enable", response_model=ControlSwitchRecord)
def enable_switch(switch_id: UUID, payload: OperatorMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ControlSwitchRecord:
    return _set_switch(switch_id, workspace_id, payload, SwitchState.ENABLED)


@router.post("/switches/{switch_id}/disable", response_model=ControlSwitchRecord)
def disable_switch(switch_id: UUID, payload: OperatorMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ControlSwitchRecord:
    return _set_switch(switch_id, workspace_id, payload, SwitchState.DISABLED)


@router.get("/audit", response_model=list[AuditRecord])
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return observability_control_service.list_audit(workspace_id)
