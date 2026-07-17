from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ManualTriggerRequest, Mutation, RunRecord, RunState, ScheduleCreate,
    ScheduleRecord, ScheduleState, SchedulerMetrics, SchedulerStatus, TickRequest,
)
from .service import temporal_scheduler_service as service

router = APIRouter(prefix="/v1/temporal-scheduler", tags=["temporal-scheduler"])


@router.get("/status", response_model=SchedulerStatus)
def get_status() -> SchedulerStatus:
    return service.status()


@router.post("/schedules", response_model=ScheduleRecord, status_code=status.HTTP_201_CREATED)
def create_schedule(payload: ScheduleCreate) -> ScheduleRecord:
    try:
        return service.create_schedule(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/schedules", response_model=list[ScheduleRecord])
def list_schedules(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ScheduleRecord]:
    return service.list_schedules(workspace_id)


@router.get("/schedules/{schedule_id}", response_model=ScheduleRecord)
def get_schedule(schedule_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> ScheduleRecord:
    item = service.get_schedule(schedule_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return item


def _set_schedule(schedule_id: UUID, workspace_id: str, payload: Mutation, state: ScheduleState) -> ScheduleRecord:
    try:
        item = service.set_state(schedule_id, workspace_id, payload, state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned schedule not found")
    return item


@router.post("/schedules/{schedule_id}/activate", response_model=ScheduleRecord)
def activate(schedule_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ScheduleRecord:
    return _set_schedule(schedule_id, workspace_id, payload, ScheduleState.ACTIVE)


@router.post("/schedules/{schedule_id}/pause", response_model=ScheduleRecord)
def pause(schedule_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ScheduleRecord:
    return _set_schedule(schedule_id, workspace_id, payload, ScheduleState.PAUSED)


@router.post("/schedules/{schedule_id}/resume", response_model=ScheduleRecord)
def resume(schedule_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ScheduleRecord:
    return _set_schedule(schedule_id, workspace_id, payload, ScheduleState.ACTIVE)


@router.post("/schedules/{schedule_id}/retire", response_model=ScheduleRecord)
def retire(schedule_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ScheduleRecord:
    return _set_schedule(schedule_id, workspace_id, payload, ScheduleState.RETIRED)


@router.post("/tick", response_model=list[RunRecord])
def evaluate_schedules(payload: TickRequest) -> list[RunRecord]:
    return service.tick(payload)


@router.post("/schedules/{schedule_id}/trigger", response_model=RunRecord, status_code=status.HTTP_201_CREATED)
def manual_trigger(schedule_id: UUID, payload: ManualTriggerRequest) -> RunRecord:
    item = service.manual_trigger(schedule_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned schedule not found")
    return item


@router.get("/runs", response_model=list[RunRecord])
def list_runs(workspace_id: str = Query(min_length=1, max_length=120), schedule_id: UUID | None = None) -> list[RunRecord]:
    return service.list_runs(workspace_id, schedule_id)


def _set_run(run_id: UUID, workspace_id: str, payload: Mutation, state: RunState) -> RunRecord:
    item = service.set_run_state(run_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=409, detail="Invalid run transition or ownership")
    return item


@router.post("/runs/{run_id}/release", response_model=RunRecord)
def release_run(run_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RunRecord:
    return _set_run(run_id, workspace_id, payload, RunState.RELEASED)


@router.post("/runs/{run_id}/succeed", response_model=RunRecord)
def succeed_run(run_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RunRecord:
    return _set_run(run_id, workspace_id, payload, RunState.SUCCEEDED)


@router.post("/runs/{run_id}/fail", response_model=RunRecord)
def fail_run(run_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RunRecord:
    return _set_run(run_id, workspace_id, payload, RunState.FAILED)


@router.post("/runs/{run_id}/cancel", response_model=RunRecord)
def cancel_run(run_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RunRecord:
    return _set_run(run_id, workspace_id, payload, RunState.CANCELLED)


@router.get("/metrics", response_model=SchedulerMetrics)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> SchedulerMetrics:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
