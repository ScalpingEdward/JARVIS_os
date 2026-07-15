from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import (
    RunStatus,
    RuntimeHeartbeat,
    RuntimeRunCreate,
    RuntimeRunRecord,
    RuntimeRunUpdate,
    RuntimeStatus,
    RuntimeSummary,
    RuntimeWorkerCreate,
    RuntimeWorkerRecord,
)


class RuntimeError(ValueError):
    pass


class AgentRuntimeService:
    def __init__(self) -> None:
        self._workers: dict[UUID, RuntimeWorkerRecord] = {}
        self._runs: dict[UUID, RuntimeRunRecord] = {}

    def reset(self) -> None:
        self._workers.clear()
        self._runs.clear()

    def register_worker(self, payload: RuntimeWorkerCreate) -> RuntimeWorkerRecord:
        if payload.provider != "mock" and payload.endpoint_url is None:
            raise RuntimeError("Non-mock runtime workers require endpoint_url")
        worker = RuntimeWorkerRecord(**payload.model_dump())
        self._workers[worker.id] = worker
        return worker

    def list_workers(self) -> list[RuntimeWorkerRecord]:
        return sorted(self._workers.values(), key=lambda item: item.created_at)

    def heartbeat(self, worker_id: UUID, payload: RuntimeHeartbeat) -> RuntimeWorkerRecord:
        worker = self._workers.get(worker_id)
        if worker is None:
            raise RuntimeError("Runtime worker not found")
        worker.status = payload.status
        worker.last_heartbeat_at = datetime.now(timezone.utc)
        return worker

    def discover(self, stale_after_seconds: int = 120) -> list[RuntimeWorkerRecord]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
        for worker in self._workers.values():
            if worker.last_heartbeat_at < cutoff:
                worker.status = RuntimeStatus.offline
        return self.list_workers()

    def create_run(self, payload: RuntimeRunCreate) -> RuntimeRunRecord:
        run = RuntimeRunRecord(**payload.model_dump())
        self._runs[run.id] = run
        return run

    def list_runs(self) -> list[RuntimeRunRecord]:
        return sorted(self._runs.values(), key=lambda item: item.created_at)

    def dispatch_next(self) -> RuntimeRunRecord:
        queued = [item for item in self.list_runs() if item.status in {RunStatus.queued, RunStatus.retrying}]
        for run in queued:
            required = set(run.required_capabilities)
            for worker in self.list_workers():
                if worker.status not in {RuntimeStatus.idle, RuntimeStatus.busy}:
                    continue
                if worker.active_runs >= worker.max_parallel_runs:
                    continue
                if not required.issubset(set(worker.capabilities)):
                    continue
                run.worker_id = worker.id
                run.status = RunStatus.running
                run.attempt += 1
                run.started_at = datetime.now(timezone.utc)
                worker.active_runs += 1
                worker.status = RuntimeStatus.busy
                return run
        raise RuntimeError("No compatible runtime worker available")

    def update_run(self, run_id: UUID, payload: RuntimeRunUpdate) -> RuntimeRunRecord:
        run = self._runs.get(run_id)
        if run is None:
            raise RuntimeError("Runtime run not found")
        worker = self._workers.get(run.worker_id) if run.worker_id else None
        terminal = {RunStatus.completed, RunStatus.failed, RunStatus.timed_out}
        run.status = payload.status
        run.output = payload.output
        run.error = payload.error
        if payload.status in terminal:
            run.finished_at = datetime.now(timezone.utc)
            if worker is not None:
                worker.active_runs = max(0, worker.active_runs - 1)
                worker.status = RuntimeStatus.idle if worker.active_runs == 0 else RuntimeStatus.busy
        return run

    def retry(self, run_id: UUID) -> RuntimeRunRecord:
        run = self._runs.get(run_id)
        if run is None:
            raise RuntimeError("Runtime run not found")
        worker = self._workers.get(run.worker_id) if run.worker_id else None
        max_retries = worker.max_retries if worker else 0
        if run.attempt > max_retries:
            raise RuntimeError("Runtime retry limit reached")
        run.worker_id = None
        run.status = RunStatus.retrying
        run.started_at = None
        run.finished_at = None
        return run

    def expire_timeouts(self) -> list[RuntimeRunRecord]:
        now = datetime.now(timezone.utc)
        expired: list[RuntimeRunRecord] = []
        for run in self._runs.values():
            if run.status != RunStatus.running or run.started_at is None or run.worker_id is None:
                continue
            worker = self._workers.get(run.worker_id)
            if worker and now - run.started_at > timedelta(seconds=worker.timeout_seconds):
                expired.append(self.update_run(run.id, RuntimeRunUpdate(status=RunStatus.timed_out, error="Run timed out")))
        return expired

    def summary(self) -> RuntimeSummary:
        workers = list(self._workers.values())
        runs = list(self._runs.values())
        return RuntimeSummary(
            workers=len(workers),
            idle_workers=sum(item.status == RuntimeStatus.idle for item in workers),
            busy_workers=sum(item.status == RuntimeStatus.busy for item in workers),
            queued_runs=sum(item.status in {RunStatus.queued, RunStatus.retrying} for item in runs),
            running_runs=sum(item.status == RunStatus.running for item in runs),
            failed_runs=sum(item.status in {RunStatus.failed, RunStatus.timed_out} for item in runs),
        )


agent_runtime_service = AgentRuntimeService()
