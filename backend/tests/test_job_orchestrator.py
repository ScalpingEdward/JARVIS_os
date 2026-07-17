from datetime import datetime, timedelta, timezone

import pytest

from app.job_orchestrator.models import (
    CompletionRequest, Heartbeat, JobCreate, JobState, LeaseRequest, Mutation,
    Priority, QueueCreate, QueueState, WorkerCreate, WorkerState,
)
from app.job_orchestrator.service import JobOrchestratorService


def active_queue(service: JobOrchestratorService, workspace: str = "w1"):
    queue = service.create_queue(QueueCreate(workspace_id=workspace, owner_id="owner", queue_key="core", allowed_job_types=["vision.analyze"]))
    return service.set_queue_state(queue.id, workspace, Mutation(requester_id="owner"), QueueState.ACTIVE)


def online_worker(service: JobOrchestratorService, queue_id, workspace: str = "w1"):
    worker = service.create_worker(WorkerCreate(workspace_id=workspace, owner_id="owner", worker_key="worker-1", queue_ids=[queue_id], capabilities=["vision.analyze"]))
    return service.heartbeat(worker.id, workspace, Heartbeat(requester_id="owner", state=WorkerState.ONLINE))


def test_priority_lease_and_success_lifecycle():
    service = JobOrchestratorService()
    queue = active_queue(service)
    worker = online_worker(service, queue.id)
    low = service.create_job(JobCreate(workspace_id="w1", owner_id="owner", queue_id=queue.id, job_type="vision.analyze", priority=Priority.LOW, idempotency_key="low", correlation_id="c1"))
    high = service.create_job(JobCreate(workspace_id="w1", owner_id="owner", queue_id=queue.id, job_type="vision.analyze", priority=Priority.HIGH, idempotency_key="high", correlation_id="c1"))
    leased = service.lease(LeaseRequest(workspace_id="w1", worker_id=worker.id, queue_id=queue.id, requester_id="owner"))
    assert leased.id == high.id
    assert service.mark_running(high.id, "w1", Mutation(requester_id="owner")).state == JobState.RUNNING
    done = service.complete(high.id, "w1", CompletionRequest(requester_id="owner", success=True, result_reference="internal://result/1"))
    assert done.state == JobState.SUCCEEDED
    assert service.list_jobs("w1", JobState.QUEUED)[0].id == low.id


def test_retry_and_dead_job_quarantine():
    service = JobOrchestratorService()
    queue = active_queue(service)
    worker = online_worker(service, queue.id)
    job = service.create_job(JobCreate(workspace_id="w1", owner_id="owner", queue_id=queue.id, job_type="vision.analyze", idempotency_key="retry", correlation_id="c2", max_retries=0))
    assert service.lease(LeaseRequest(workspace_id="w1", worker_id=worker.id, queue_id=queue.id, requester_id="owner")).id == job.id
    dead = service.complete(job.id, "w1", CompletionRequest(requester_id="owner", success=False, reason="bad input"))
    assert dead.state == JobState.DEAD
    assert service.dead_jobs("w1")[0].id == job.id


def test_schedule_idempotency_isolation_and_safety():
    service = JobOrchestratorService()
    queue = active_queue(service)
    worker = online_worker(service, queue.id)
    future = service.create_job(JobCreate(workspace_id="w1", owner_id="owner", queue_id=queue.id, job_type="vision.analyze", idempotency_key="future", correlation_id="c3", scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1)))
    assert service.lease(LeaseRequest(workspace_id="w1", worker_id=worker.id, queue_id=queue.id, requester_id="owner")) is None
    with pytest.raises(ValueError):
        service.create_job(JobCreate(workspace_id="w1", owner_id="owner", queue_id=queue.id, job_type="vision.analyze", idempotency_key="future", correlation_id="c4"))
    assert service.set_queue_state(queue.id, "w2", Mutation(requester_id="owner"), QueueState.SUSPENDED) is None
    with pytest.raises(ValueError):
        WorkerCreate(workspace_id="w1", owner_id="owner", worker_key="unsafe", queue_ids=[queue.id], execute_jobs=True)
    with pytest.raises(ValueError):
        LeaseRequest(workspace_id="w1", worker_id=worker.id, queue_id=queue.id, requester_id="owner", execute_job=True)
    assert future.state == JobState.QUEUED
