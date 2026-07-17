from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    CompletionRequest, Heartbeat, JobCreate, JobOrchestratorStatus, JobRecord,
    JobState, LeaseRequest, MetricsRecord, Mutation, QueueCreate, QueueRecord,
    QueueState, WorkerCreate, WorkerRecord,
)
from .service import job_orchestrator_service as service

router = APIRouter(prefix="/v1/job-orchestrator", tags=["job-orchestrator"])


@router.get("/status", response_model=JobOrchestratorStatus)
def get_status() -> JobOrchestratorStatus:
    return service.status()


@router.post("/queues", response_model=QueueRecord, status_code=status.HTTP_201_CREATED)
def create_queue(payload: QueueCreate) -> QueueRecord:
    try:
        return service.create_queue(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/queues", response_model=list[QueueRecord])
def list_queues(workspace_id: str = Query(min_length=1, max_length=120)) -> list[QueueRecord]:
    return service.list_queues(workspace_id)


def _set_queue(queue_id: UUID, workspace_id: str, payload: Mutation, state: QueueState) -> QueueRecord:
    item = service.set_queue_state(queue_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned queue not found")
    return item


@router.post("/queues/{queue_id}/activate", response_model=QueueRecord)
def activate_queue(queue_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> QueueRecord:
    return _set_queue(queue_id, workspace_id, payload, QueueState.ACTIVE)


@router.post("/queues/{queue_id}/suspend", response_model=QueueRecord)
def suspend_queue(queue_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> QueueRecord:
    return _set_queue(queue_id, workspace_id, payload, QueueState.SUSPENDED)


@router.post("/queues/{queue_id}/retire", response_model=QueueRecord)
def retire_queue(queue_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> QueueRecord:
    return _set_queue(queue_id, workspace_id, payload, QueueState.RETIRED)


@router.post("/workers", response_model=WorkerRecord, status_code=status.HTTP_201_CREATED)
def create_worker(payload: WorkerCreate) -> WorkerRecord:
    try:
        return service.create_worker(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/workers", response_model=list[WorkerRecord])
def list_workers(workspace_id: str = Query(min_length=1, max_length=120)) -> list[WorkerRecord]:
    return service.list_workers(workspace_id)


@router.post("/workers/{worker_id}/heartbeat", response_model=WorkerRecord)
def heartbeat(worker_id: UUID, payload: Heartbeat, workspace_id: str = Query(min_length=1, max_length=120)) -> WorkerRecord:
    item = service.heartbeat(worker_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned worker not found")
    return item


@router.post("/jobs", response_model=JobRecord, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate) -> JobRecord:
    try:
        return service.create_job(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/jobs", response_model=list[JobRecord])
def list_jobs(workspace_id: str = Query(min_length=1, max_length=120), state: JobState | None = None) -> list[JobRecord]:
    return service.list_jobs(workspace_id, state)


@router.post("/jobs/lease", response_model=JobRecord)
def lease_job(payload: LeaseRequest) -> JobRecord:
    item = service.lease(payload)
    if item is None:
        raise HTTPException(status_code=404, detail="No eligible job or worker")
    return item


@router.post("/jobs/{job_id}/running", response_model=JobRecord)
def mark_running(job_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> JobRecord:
    item = service.mark_running(job_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=409, detail="Invalid job transition or ownership")
    return item


@router.post("/jobs/{job_id}/complete", response_model=JobRecord)
def complete_job(job_id: UUID, payload: CompletionRequest, workspace_id: str = Query(min_length=1, max_length=120)) -> JobRecord:
    item = service.complete(job_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=409, detail="Invalid job transition or ownership")
    return item


@router.post("/jobs/{job_id}/cancel", response_model=JobRecord)
def cancel_job(job_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> JobRecord:
    item = service.cancel(job_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=409, detail="Job cannot be cancelled")
    return item


@router.get("/dead-jobs", response_model=list[JobRecord])
def dead_jobs(workspace_id: str = Query(min_length=1, max_length=120)) -> list[JobRecord]:
    return service.dead_jobs(workspace_id)


@router.get("/metrics", response_model=MetricsRecord)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
