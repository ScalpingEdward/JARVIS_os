from datetime import datetime, timezone
from uuid import UUID

import httpx

from app.db import SessionLocal
from app.orchestrator.models import TaskStatus
from app.orchestrator.service import orchestrator_service
from app.persistence import PersistenceRepository

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
    """Registers worker endpoints and persists every dispatch lifecycle."""

    def __init__(self) -> None:
        self._workers: dict[UUID, WorkerEndpointRecord] = {}

    def reset(self) -> None:
        self._workers.clear()

    def register(self, payload: WorkerEndpointCreate) -> WorkerEndpointRecord:
        if payload.worker_type != WorkerType.mock and payload.endpoint_url is None:
            raise WorkerGatewayError("A non-mock worker requires endpoint_url")
        worker = WorkerEndpointRecord(**payload.model_dump())
        self._workers[worker.id] = worker
        return worker

    def list_workers(self) -> list[WorkerEndpointRecord]:
        return sorted(self._workers.values(), key=lambda item: item.created_at)

    def list_dispatches(self) -> list[DispatchRecord]:
        with SessionLocal() as session:
            rows = PersistenceRepository(session).list_worker_runs()
            return [
                DispatchRecord(
                    id=UUID(row.id),
                    task_id=UUID(row.task_id),
                    worker_id=UUID(row.worker_name),
                    status=DispatchStatus(row.status),
                    external_run_id=row.external_run_id,
                    output=row.result,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ]

    def dispatch(self, task_id: UUID, worker_id: UUID) -> DispatchRecord:
        task = orchestrator_service.get_task(task_id)
        worker = self._workers.get(worker_id)
        if task is None:
            raise WorkerGatewayError("Task not found")
        if worker is None or not worker.enabled:
            raise WorkerGatewayError("Worker not found or disabled")
        if not set(task.required_capabilities).issubset(set(worker.capabilities)):
            raise WorkerGatewayError("Worker lacks required capabilities")

        record = DispatchRecord(task_id=task.id, worker_id=worker.id)
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
                self._save_dispatch(record, worker.worker_type.value)
                raise WorkerGatewayError("Worker dispatch failed") from exc

        record.updated_at = datetime.now(timezone.utc)
        self._save_dispatch(record, worker.worker_type.value)
        return record

    def callback(self, dispatch_id: UUID, payload: WorkerCallback) -> DispatchRecord | None:
        record = next((item for item in self.list_dispatches() if item.id == dispatch_id), None)
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
        worker = self._workers.get(record.worker_id)
        self._save_dispatch(record, worker.worker_type.value if worker else "unknown")
        return record

    @staticmethod
    def _save_dispatch(record: DispatchRecord, provider: str) -> None:
        with SessionLocal() as session:
            PersistenceRepository(session).save_worker_run(
                {
                    "id": str(record.id),
                    "task_id": str(record.task_id),
                    "worker_name": str(record.worker_id),
                    "provider": provider,
                    "external_run_id": record.external_run_id,
                    "status": record.status.value,
                    "result": record.output or record.error,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                }
            )


worker_gateway_service = WorkerGatewayService()
