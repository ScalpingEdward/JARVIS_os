from datetime import datetime, timezone
from uuid import UUID

import httpx

from app.orchestrator.models import TaskStatus
from app.orchestrator.service import orchestrator_service

from .models import (
    DispatchRecord,
    DispatchStatus,
    WorkerCallback,
    WorkerEndpointCreate,
    WorkerEndpointRecord,
    WorkerType,
)


class WorkerGatewayError(RuntimeError):
    pass


class WorkerGatewayService:
    """Registers worker endpoints and dispatches orchestrator tasks safely."""

    def __init__(self) -> None:
        self._workers: dict[UUID, WorkerEndpointRecord] = {}
        self._dispatches: dict[UUID, DispatchRecord] = {}

    def reset(self) -> None:
        self._workers.clear()
        self._dispatches.clear()

    def register(self, payload: WorkerEndpointCreate) -> WorkerEndpointRecord:
        if payload.worker_type != WorkerType.mock and payload.endpoint_url is None:
            raise WorkerGatewayError("A non-mock worker requires endpoint_url")
        worker = WorkerEndpointRecord(**payload.model_dump())
        self._workers[worker.id] = worker
        return worker

    def list_workers(self) -> list[WorkerEndpointRecord]:
        return sorted(self._workers.values(), key=lambda item: item.created_at)

    def list_dispatches(self) -> list[DispatchRecord]:
        return sorted(self._dispatches.values(), key=lambda item: item.created_at)

    def dispatch(self, task_id: UUID, worker_id: UUID) -> DispatchRecord:
        task = orchestrator_service.get_task(task_id)
        worker = self._workers.get(worker_id)
        if task is None:
            raise WorkerGatewayError("Task not found")
        if worker is None or not worker.enabled:
            raise WorkerGatewayError("Worker not found or disabled")
        required = set(task.required_capabilities)
        if not required.issubset(set(worker.capabilities)):
            raise WorkerGatewayError("Worker lacks required capabilities")

        record = DispatchRecord(task_id=task.id, worker_id=worker.id)
        self._dispatches[record.id] = record
        orchestrator_service.update_task_status(task.id, TaskStatus.in_progress)

        if worker.worker_type == WorkerType.mock:
            record.status = DispatchStatus.running
            record.external_run_id = f"mock-{record.id}"
        else:
            payload = {
                "dispatch_id": str(record.id),
                "task": task.model_dump(mode="json"),
                "worker": worker.model_dump(mode="json"),
            }
            try:
                response = httpx.post(str(worker.endpoint_url), json=payload, timeout=15.0)
                response.raise_for_status()
                data = response.json() if response.content else {}
                record.external_run_id = data.get("run_id")
                record.status = DispatchStatus.running
            except (httpx.HTTPError, ValueError) as exc:
                record.status = DispatchStatus.failed
                record.error = str(exc)
                orchestrator_service.update_task_status(task.id, TaskStatus.failed)
                raise WorkerGatewayError("Worker dispatch failed") from exc

        record.updated_at = datetime.now(timezone.utc)
        return record

    def callback(self, dispatch_id: UUID, payload: WorkerCallback) -> DispatchRecord | None:
        record = self._dispatches.get(dispatch_id)
        if record is None:
            return None
        record.status = payload.status
        record.external_run_id = payload.external_run_id or record.external_run_id
        record.output = payload.output
        record.error = payload.error
        record.updated_at = datetime.now(timezone.utc)
        mapped = {
            DispatchStatus.completed: TaskStatus.completed,
            DispatchStatus.failed: TaskStatus.failed,
            DispatchStatus.running: TaskStatus.in_progress,
            DispatchStatus.accepted: TaskStatus.assigned,
        }
        orchestrator_service.update_task_status(record.task_id, mapped[payload.status])
        return record


worker_gateway_service = WorkerGatewayService()
