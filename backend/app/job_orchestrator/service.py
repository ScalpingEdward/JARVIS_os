from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import (
    AuditRecord, CompletionRequest, Heartbeat, JobCreate, JobOrchestratorStatus,
    JobRecord, JobState, LeaseRequest, MetricsRecord, Mutation, Priority,
    QueueCreate, QueueRecord, QueueState, WorkerCreate, WorkerRecord, WorkerState,
)


_PRIORITY = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.NORMAL: 2,
    Priority.LOW: 3,
    Priority.BACKGROUND: 4,
}


class JobOrchestratorService:
    def __init__(self) -> None:
        self.queues: dict[UUID, QueueRecord] = {}
        self.workers: dict[UUID, WorkerRecord] = {}
        self.jobs: dict[UUID, JobRecord] = {}
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, **details) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, action=action, entity_type=entity_type, entity_id=entity_id, actor_id=actor_id, details=details))

    def _refresh(self) -> None:
        now = datetime.now(timezone.utc)
        for job in self.jobs.values():
            if job.state in {JobState.LEASED, JobState.RUNNING} and job.lease_expires_at and job.lease_expires_at <= now:
                worker = self.workers.get(job.leased_by_worker_id) if job.leased_by_worker_id else None
                if worker and job.id in worker.active_job_ids:
                    worker.active_job_ids.remove(job.id)
                job.leased_by_worker_id = None
                job.lease_expires_at = None
                if job.retry_count < job.max_retries:
                    job.retry_count += 1
                    job.state = JobState.RETRY_WAIT
                    job.next_attempt_at = now + timedelta(seconds=job.backoff_seconds * max(job.retry_count, 1))
                else:
                    job.state = JobState.DEAD
                    job.failure_reason = "lease expired after retry exhaustion"
                job.updated_at = now
            if job.state == JobState.RETRY_WAIT and job.next_attempt_at and job.next_attempt_at <= now:
                job.state = JobState.QUEUED
                job.next_attempt_at = None
                job.updated_at = now

    def status(self) -> JobOrchestratorStatus:
        self._refresh()
        return JobOrchestratorStatus(queues=len(self.queues), workers=len(self.workers), jobs=len(self.jobs), dead_jobs=sum(j.state == JobState.DEAD for j in self.jobs.values()))

    def create_queue(self, payload: QueueCreate) -> QueueRecord:
        if any(q.workspace_id == payload.workspace_id and q.queue_key == payload.queue_key and q.state != QueueState.RETIRED for q in self.queues.values()):
            raise ValueError("active queue key already exists")
        item = QueueRecord(**payload.model_dump())
        self.queues[item.id] = item
        self._audit(item.workspace_id, "queue.created", "queue", item.id, item.owner_id)
        return item

    def list_queues(self, workspace_id: str) -> list[QueueRecord]:
        return [q for q in self.queues.values() if q.workspace_id == workspace_id]

    def set_queue_state(self, queue_id: UUID, workspace_id: str, payload: Mutation, state: QueueState) -> QueueRecord | None:
        item = self.queues.get(queue_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"queue.{state.value}", "queue", item.id, payload.requester_id, reason=payload.reason)
        return item

    def create_worker(self, payload: WorkerCreate) -> WorkerRecord:
        queues = [self.queues.get(i) for i in payload.queue_ids]
        if any(q is None or q.workspace_id != payload.workspace_id for q in queues):
            raise ValueError("invalid workspace queue reference")
        if any(w.workspace_id == payload.workspace_id and w.worker_key == payload.worker_key and w.state != WorkerState.OFFLINE for w in self.workers.values()):
            raise ValueError("active worker key already exists")
        item = WorkerRecord(**payload.model_dump())
        self.workers[item.id] = item
        self._audit(item.workspace_id, "worker.registered", "worker", item.id, item.owner_id)
        return item

    def list_workers(self, workspace_id: str) -> list[WorkerRecord]:
        return [w for w in self.workers.values() if w.workspace_id == workspace_id]

    def heartbeat(self, worker_id: UUID, workspace_id: str, payload: Heartbeat) -> WorkerRecord | None:
        item = self.workers.get(worker_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.state = payload.state
        item.last_heartbeat_at = datetime.now(timezone.utc)
        item.updated_at = item.last_heartbeat_at
        self._audit(workspace_id, "worker.heartbeat", "worker", item.id, payload.requester_id, state=payload.state.value)
        return item

    def create_job(self, payload: JobCreate) -> JobRecord:
        queue = self.queues.get(payload.queue_id)
        if not queue or queue.workspace_id != payload.workspace_id or queue.state != QueueState.ACTIVE:
            raise ValueError("active workspace queue not found")
        if queue.allowed_job_types and payload.job_type not in queue.allowed_job_types:
            raise ValueError("job type is not allowed by queue")
        duplicate = next((j for j in self.jobs.values() if j.workspace_id == payload.workspace_id and j.idempotency_key == payload.idempotency_key and j.state != JobState.CANCELLED), None)
        if duplicate:
            raise ValueError("idempotency key already exists")
        data = payload.model_dump(exclude={"human_approved", "execute_action"})
        item = JobRecord(**data, lease_seconds=payload.lease_seconds or queue.default_lease_seconds)
        self.jobs[item.id] = item
        self._audit(item.workspace_id, "job.queued", "job", item.id, item.owner_id, job_type=item.job_type)
        return item

    def list_jobs(self, workspace_id: str, state: JobState | None = None) -> list[JobRecord]:
        self._refresh()
        return [j for j in self.jobs.values() if j.workspace_id == workspace_id and (state is None or j.state == state)]

    def lease(self, payload: LeaseRequest) -> JobRecord | None:
        self._refresh()
        worker = self.workers.get(payload.worker_id)
        queue = self.queues.get(payload.queue_id)
        if not worker or not queue or worker.workspace_id != payload.workspace_id or queue.workspace_id != payload.workspace_id:
            return None
        if worker.owner_id != payload.requester_id or worker.state not in {WorkerState.ONLINE, WorkerState.BUSY}:
            return None
        if payload.queue_id not in worker.queue_ids or len(worker.active_job_ids) >= worker.max_parallel_jobs:
            return None
        now = datetime.now(timezone.utc)
        candidates = [j for j in self.jobs.values() if j.workspace_id == payload.workspace_id and j.queue_id == payload.queue_id and j.state == JobState.QUEUED and (j.scheduled_at is None or j.scheduled_at <= now)]
        if not candidates:
            return None
        candidates.sort(key=lambda j: (_PRIORITY[j.priority], j.created_at))
        job = candidates[0]
        job.state = JobState.LEASED
        job.leased_by_worker_id = worker.id
        job.lease_expires_at = now + timedelta(seconds=job.lease_seconds)
        job.updated_at = now
        worker.active_job_ids.append(job.id)
        worker.state = WorkerState.BUSY
        worker.updated_at = now
        self._audit(job.workspace_id, "job.leased", "job", job.id, payload.requester_id, worker_id=str(worker.id))
        return job

    def mark_running(self, job_id: UUID, workspace_id: str, payload: Mutation) -> JobRecord | None:
        job = self.jobs.get(job_id)
        worker = self.workers.get(job.leased_by_worker_id) if job and job.leased_by_worker_id else None
        if not job or job.workspace_id != workspace_id or job.state != JobState.LEASED or not worker or worker.owner_id != payload.requester_id:
            return None
        job.state = JobState.RUNNING
        job.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "job.running", "job", job.id, payload.requester_id)
        return job

    def complete(self, job_id: UUID, workspace_id: str, payload: CompletionRequest) -> JobRecord | None:
        job = self.jobs.get(job_id)
        worker = self.workers.get(job.leased_by_worker_id) if job and job.leased_by_worker_id else None
        if not job or job.workspace_id != workspace_id or job.state not in {JobState.LEASED, JobState.RUNNING} or not worker or worker.owner_id != payload.requester_id:
            return None
        if job.id in worker.active_job_ids:
            worker.active_job_ids.remove(job.id)
        worker.state = WorkerState.ONLINE if not worker.active_job_ids else WorkerState.BUSY
        job.leased_by_worker_id = None
        job.lease_expires_at = None
        job.result_reference = payload.result_reference
        job.failure_reason = None if payload.success else payload.reason
        now = datetime.now(timezone.utc)
        if payload.success:
            job.state = JobState.SUCCEEDED
        elif job.retry_count < job.max_retries:
            job.retry_count += 1
            job.state = JobState.RETRY_WAIT
            job.next_attempt_at = now + timedelta(seconds=job.backoff_seconds * max(job.retry_count, 1))
        else:
            job.state = JobState.DEAD
        job.updated_at = now
        self._audit(workspace_id, f"job.{job.state.value}", "job", job.id, payload.requester_id, reason=payload.reason)
        return job

    def cancel(self, job_id: UUID, workspace_id: str, payload: Mutation) -> JobRecord | None:
        job = self.jobs.get(job_id)
        if not job or job.workspace_id != workspace_id or job.owner_id != payload.requester_id or job.state in {JobState.SUCCEEDED, JobState.DEAD}:
            return None
        job.state = JobState.CANCELLED
        job.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "job.cancelled", "job", job.id, payload.requester_id, reason=payload.reason)
        return job

    def dead_jobs(self, workspace_id: str) -> list[JobRecord]:
        self._refresh()
        return [j for j in self.jobs.values() if j.workspace_id == workspace_id and j.state == JobState.DEAD]

    def metrics(self, workspace_id: str) -> MetricsRecord:
        self._refresh()
        jobs = [j for j in self.jobs.values() if j.workspace_id == workspace_id]
        workers = [w for w in self.workers.values() if w.workspace_id == workspace_id]
        return MetricsRecord(
            workspace_id=workspace_id,
            queues=sum(q.workspace_id == workspace_id for q in self.queues.values()),
            workers=len(workers), online_workers=sum(w.state in {WorkerState.ONLINE, WorkerState.BUSY} for w in workers),
            queued_jobs=sum(j.state == JobState.QUEUED for j in jobs), leased_jobs=sum(j.state in {JobState.LEASED, JobState.RUNNING} for j in jobs),
            retry_wait_jobs=sum(j.state == JobState.RETRY_WAIT for j in jobs), succeeded_jobs=sum(j.state == JobState.SUCCEEDED for j in jobs),
            failed_jobs=sum(j.state == JobState.FAILED for j in jobs), dead_jobs=sum(j.state == JobState.DEAD for j in jobs),
        )

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [a for a in self.audit if a.workspace_id == workspace_id]


job_orchestrator_service = JobOrchestratorService()
