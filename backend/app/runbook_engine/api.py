from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import ApprovalCreate, ApprovalRecord, MetricsRecord, Mutation, RunbookCreate, RunbookRecord, RunbookState, RunbookStatus, RunCreate, RunRecord, RunState, StepResultCreate, StepResultRecord
from .service import runbook_service as service

router = APIRouter(prefix="/v1/runbooks", tags=["runbooks"])

@router.get("/status", response_model=RunbookStatus)
def get_status() -> RunbookStatus:
    return service.status()

@router.post("", response_model=RunbookRecord, status_code=status.HTTP_201_CREATED)
def create_runbook(payload: RunbookCreate) -> RunbookRecord:
    try:
        return service.create_runbook(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.get("", response_model=list[RunbookRecord])
def list_runbooks(workspace_id: str = Query(min_length=1, max_length=120), state: RunbookState | None = None) -> list[RunbookRecord]:
    return service.list_runbooks(workspace_id, state)

@router.get("/{runbook_id}", response_model=RunbookRecord)
def get_runbook(runbook_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> RunbookRecord:
    item = service.get_runbook(runbook_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Runbook not found")
    return item

def _set_runbook(runbook_id: UUID, workspace_id: str, payload: Mutation, state: RunbookState) -> RunbookRecord:
    try:
        item = service.set_state(runbook_id, workspace_id, payload, state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned runbook not found")
    return item

@router.post("/{runbook_id}/review", response_model=RunbookRecord)
def submit_review(runbook_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RunbookRecord:
    return _set_runbook(runbook_id, workspace_id, payload, RunbookState.REVIEW)

@router.post("/approvals", response_model=ApprovalRecord, status_code=status.HTTP_201_CREATED)
def approve(payload: ApprovalCreate) -> ApprovalRecord:
    try:
        return service.approve(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.post("/{runbook_id}/publish", response_model=RunbookRecord)
def publish(runbook_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RunbookRecord:
    return _set_runbook(runbook_id, workspace_id, payload, RunbookState.PUBLISHED)

@router.post("/{runbook_id}/retire", response_model=RunbookRecord)
def retire(runbook_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RunbookRecord:
    return _set_runbook(runbook_id, workspace_id, payload, RunbookState.RETIRED)

@router.post("/runs", response_model=RunRecord, status_code=status.HTTP_201_CREATED)
def create_run(payload: RunCreate) -> RunRecord:
    try:
        return service.create_run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.get("/runs/list", response_model=list[RunRecord])
def list_runs(workspace_id: str = Query(min_length=1, max_length=120), runbook_id: UUID | None = None) -> list[RunRecord]:
    return service.list_runs(workspace_id, runbook_id)

def _set_run(run_id: UUID, workspace_id: str, payload: Mutation, state: RunState) -> RunRecord:
    try:
        item = service.set_run_state(run_id, workspace_id, payload, state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Assigned run not found")
    return item

@router.post("/runs/{run_id}/start", response_model=RunRecord)
def start_run(run_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RunRecord:
    return _set_run(run_id, workspace_id, payload, RunState.IN_PROGRESS)

@router.post("/runs/{run_id}/cancel", response_model=RunRecord)
def cancel_run(run_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RunRecord:
    return _set_run(run_id, workspace_id, payload, RunState.CANCELLED)

@router.post("/steps", response_model=StepResultRecord, status_code=status.HTTP_201_CREATED)
def record_step(payload: StepResultCreate) -> StepResultRecord:
    try:
        return service.record_step(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.get("/runs/{run_id}/steps", response_model=list[StepResultRecord])
def list_step_results(run_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> list[StepResultRecord]:
    return service.list_step_results(workspace_id, run_id)

@router.get("/metrics", response_model=MetricsRecord)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)

@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
