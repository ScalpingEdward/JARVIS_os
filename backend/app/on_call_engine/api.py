from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AcknowledgeCreate, CoverageRecord, EscalationCreate, EscalationRecord,
    EscalationState, HandoverCreate, HandoverRecord, MetricsRecord, Mutation,
    OnCallStatus, ScheduleCreate, ScheduleRecord, ScheduleState,
)
from .service import on_call_service as service

router = APIRouter(prefix="/v1/on-call", tags=["on-call"])


@router.get("/status", response_model=OnCallStatus)
def get_status() -> OnCallStatus:
    return service.status()


@router.post("/schedules", response_model=ScheduleRecord, status_code=status.HTTP_201_CREATED)
def create_schedule(payload: ScheduleCreate) -> ScheduleRecord:
    try:
        return service.create_schedule(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/schedules", response_model=list[ScheduleRecord])
def list_schedules(workspace_id: str = Query(min_length=1, max_length=120), state: ScheduleState | None = None) -> list[ScheduleRecord]:
    return service.list_schedules(workspace_id, state)


@router.get("/schedules/{schedule_id}", response_model=ScheduleRecord)
def get_schedule(schedule_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> ScheduleRecord:
    item = service.get_schedule(schedule_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="On-call schedule not found")
    return item


def _set_schedule(schedule_id: UUID, workspace_id: str, payload: Mutation, state: ScheduleState) -> ScheduleRecord:
    try:
        item = service.set_schedule_state(schedule_id, workspace_id, payload, state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned on-call schedule not found")
    return item


@router.post("/schedules/{schedule_id}/activate", response_model=ScheduleRecord)
def activate(schedule_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ScheduleRecord:
    return _set_schedule(schedule_id, workspace_id, payload, ScheduleState.ACTIVE)


@router.post("/schedules/{schedule_id}/pause", response_model=ScheduleRecord)
def pause(schedule_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ScheduleRecord:
    return _set_schedule(schedule_id, workspace_id, payload, ScheduleState.PAUSED)


@router.post("/schedules/{schedule_id}/retire", response_model=ScheduleRecord)
def retire(schedule_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ScheduleRecord:
    return _set_schedule(schedule_id, workspace_id, payload, ScheduleState.RETIRED)


@router.post("/handovers", response_model=HandoverRecord, status_code=status.HTTP_201_CREATED)
def create_handover(payload: HandoverCreate) -> HandoverRecord:
    try:
        return service.create_handover(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/handovers", response_model=list[HandoverRecord])
def list_handovers(workspace_id: str = Query(min_length=1, max_length=120), schedule_id: UUID | None = None) -> list[HandoverRecord]:
    return service.list_handovers(workspace_id, schedule_id)


@router.get("/schedules/{schedule_id}/coverage", response_model=CoverageRecord)
def coverage(schedule_id: UUID, workspace_id: str = Query(min_length=1, max_length=120), at: datetime | None = None) -> CoverageRecord:
    try:
        return service.coverage(workspace_id, schedule_id, at)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/escalations", response_model=EscalationRecord, status_code=status.HTTP_201_CREATED)
def create_escalation(payload: EscalationCreate) -> EscalationRecord:
    try:
        return service.create_escalation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/escalations", response_model=list[EscalationRecord])
def list_escalations(workspace_id: str = Query(min_length=1, max_length=120), state: EscalationState | None = None) -> list[EscalationRecord]:
    return service.list_escalations(workspace_id, state)


@router.post("/escalations/{escalation_id}/notified", response_model=EscalationRecord)
def mark_notified(escalation_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> EscalationRecord:
    item = service.mark_notified(escalation_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return item


@router.post("/escalations/acknowledge", response_model=EscalationRecord)
def acknowledge(payload: AcknowledgeCreate) -> EscalationRecord:
    try:
        return service.acknowledge(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/escalations/evaluate", response_model=list[EscalationRecord])
def evaluate_due(workspace_id: str, requester_id: str, evaluation_time: datetime | None = None) -> list[EscalationRecord]:
    return service.escalate_due(workspace_id, requester_id, evaluation_time)


@router.post("/escalations/{escalation_id}/resolve", response_model=EscalationRecord)
def resolve(escalation_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> EscalationRecord:
    try:
        item = service.resolve(escalation_id, workspace_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Assigned escalation not found")
    return item


@router.get("/metrics", response_model=MetricsRecord)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
