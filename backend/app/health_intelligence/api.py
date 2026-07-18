from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AlertRecord, AlertState, HealthIntelligenceStatus, HealthRuleCreate,
    HealthRuleRecord, HealthSnapshot, MetricsRecord, Mutation,
    TelemetryCreate, TelemetryRecord,
)
from .service import health_intelligence_service as service

router = APIRouter(prefix="/v1/health-intelligence", tags=["health-intelligence"])


@router.get("/status", response_model=HealthIntelligenceStatus)
def get_status() -> HealthIntelligenceStatus:
    return service.status()


@router.post("/telemetry", response_model=TelemetryRecord, status_code=status.HTTP_201_CREATED)
def record_telemetry(payload: TelemetryCreate) -> TelemetryRecord:
    return service.record_telemetry(payload)


@router.get("/telemetry", response_model=list[TelemetryRecord])
def list_telemetry(
    workspace_id: str = Query(min_length=1, max_length=120),
    target_key: str | None = Query(default=None, max_length=240),
) -> list[TelemetryRecord]:
    return service.list_telemetry(workspace_id, target_key)


@router.post("/rules", response_model=HealthRuleRecord, status_code=status.HTTP_201_CREATED)
def create_rule(payload: HealthRuleCreate) -> HealthRuleRecord:
    try:
        return service.create_rule(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/rules", response_model=list[HealthRuleRecord])
def list_rules(workspace_id: str = Query(min_length=1, max_length=120)) -> list[HealthRuleRecord]:
    return service.list_rules(workspace_id)


@router.get("/snapshots", response_model=list[HealthSnapshot])
def snapshots(workspace_id: str = Query(min_length=1, max_length=120)) -> list[HealthSnapshot]:
    return service.snapshots(workspace_id)


@router.get("/alerts", response_model=list[AlertRecord])
def list_alerts(
    workspace_id: str = Query(min_length=1, max_length=120),
    state: AlertState | None = None,
) -> list[AlertRecord]:
    return service.list_alerts(workspace_id, state)


def _mutate_alert(alert_id: UUID, workspace_id: str, payload: Mutation, target: AlertState) -> AlertRecord:
    try:
        item = service.mutate_alert(alert_id, workspace_id, payload, target)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return item


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertRecord)
def acknowledge_alert(alert_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AlertRecord:
    return _mutate_alert(alert_id, workspace_id, payload, AlertState.ACKNOWLEDGED)


@router.post("/alerts/{alert_id}/resolve", response_model=AlertRecord)
def resolve_alert(alert_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AlertRecord:
    return _mutate_alert(alert_id, workspace_id, payload, AlertState.RESOLVED)


@router.post("/alerts/{alert_id}/archive", response_model=AlertRecord)
def archive_alert(alert_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AlertRecord:
    return _mutate_alert(alert_id, workspace_id, payload, AlertState.ARCHIVED)


@router.get("/metrics", response_model=MetricsRecord)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
