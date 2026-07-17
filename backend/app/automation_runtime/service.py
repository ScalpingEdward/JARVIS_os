from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import (
    AutomationJobCreate,
    AutomationJobRecord,
    ConnectorMutation,
    ConnectorRecord,
    ConnectorRegister,
    ConnectorState,
    JobApproval,
    JobCompletion,
    JobState,
    RuntimeStatus,
)


class AutomationRuntimeService:
    def __init__(self) -> None:
        self._connectors: dict[UUID, ConnectorRecord] = {}
        self._jobs: dict[UUID, AutomationJobRecord] = {}
        self._idempotency: dict[tuple[str, str], UUID] = {}

    def status(self) -> RuntimeStatus:
        jobs = list(self._jobs.values())
        connectors = list(self._connectors.values())
        return RuntimeStatus(
            registered_connectors=len(connectors),
            active_connectors=sum(item.state == ConnectorState.ACTIVE for item in connectors),
            queued_jobs=sum(item.state in {JobState.QUEUED, JobState.READY} for item in jobs),
            waiting_approval_jobs=sum(item.state == JobState.WAITING_APPROVAL for item in jobs),
            running_jobs=sum(item.state == JobState.RUNNING for item in jobs),
            completed_jobs=sum(item.state == JobState.COMPLETED for item in jobs),
            failed_jobs=sum(item.state == JobState.FAILED for item in jobs),
            blocked_jobs=sum(item.state == JobState.BLOCKED for item in jobs),
        )

    def register_connector(self, payload: ConnectorRegister) -> ConnectorRecord:
        duplicate = any(
            item.workspace_id == payload.workspace_id.strip()
            and item.connector_key == payload.connector_key.strip().lower()
            for item in self._connectors.values()
        )
        if duplicate:
            raise ValueError("connector key already exists in workspace")
        record = ConnectorRecord(
            workspace_id=payload.workspace_id.strip(),
            owner_id=payload.owner_id.strip(),
            connector_key=payload.connector_key.strip().lower(),
            connector_type=payload.connector_type,
            display_name=payload.display_name.strip(),
            capabilities=self._normalize(payload.capabilities),
            actions=self._normalize(payload.actions),
            rate_limit_per_minute=payload.rate_limit_per_minute,
            supports_dry_run=payload.supports_dry_run,
        )
        self._connectors[record.id] = record
        return record

    def list_connectors(self, workspace_id: str) -> list[ConnectorRecord]:
        return sorted(
            [item for item in self._connectors.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
        )

    def get_connector(self, connector_id: UUID, workspace_id: str) -> ConnectorRecord | None:
        record = self._connectors.get(connector_id)
        return record if record and record.workspace_id == workspace_id else None

    def activate_connector(
        self,
        connector_id: UUID,
        workspace_id: str,
        requester_id: str,
        payload: ConnectorMutation,
    ) -> ConnectorRecord | None:
        connector = self._owned_connector(connector_id, workspace_id, requester_id)
        if connector is None:
            return None
        connector.state = ConnectorState.ACTIVE
        connector.health_message = payload.reason.strip() or "Active"
        connector.updated_at = datetime.now(timezone.utc)
        return connector

    def disable_connector(
        self,
        connector_id: UUID,
        workspace_id: str,
        requester_id: str,
        payload: ConnectorMutation,
    ) -> ConnectorRecord | None:
        connector = self._owned_connector(connector_id, workspace_id, requester_id)
        if connector is None:
            return None
        connector.state = ConnectorState.DISABLED
        connector.health_message = payload.reason.strip() or "Disabled"
        connector.updated_at = datetime.now(timezone.utc)
        return connector

    def heartbeat(
        self,
        connector_id: UUID,
        workspace_id: str,
        healthy: bool,
        message: str,
    ) -> ConnectorRecord | None:
        connector = self.get_connector(connector_id, workspace_id)
        if connector is None:
            return None
        connector.last_heartbeat_at = datetime.now(timezone.utc)
        connector.health_message = message.strip() or ("Healthy" if healthy else "Degraded")
        if connector.state != ConnectorState.DISABLED:
            connector.state = ConnectorState.ACTIVE if healthy else ConnectorState.DEGRADED
        connector.updated_at = datetime.now(timezone.utc)
        return connector

    def create_job(self, payload: AutomationJobCreate) -> AutomationJobRecord:
        existing_id = self._idempotency.get((payload.workspace_id.strip(), payload.idempotency_key.strip()))
        if existing_id is not None:
            return self._jobs[existing_id]

        connector = self.get_connector(payload.connector_id, payload.workspace_id.strip())
        if connector is None:
            state, reason = JobState.BLOCKED, "Connector not found in workspace."
        elif connector.state != ConnectorState.ACTIVE:
            state, reason = JobState.BLOCKED, "Connector is not active."
        elif payload.action.strip().lower() not in connector.actions:
            state, reason = JobState.BLOCKED, "Action is not declared by connector."
        elif not connector.supports_dry_run:
            state, reason = JobState.BLOCKED, "Connector does not support dry-run execution."
        elif payload.requires_human_approval and not payload.human_approved:
            state, reason = JobState.WAITING_APPROVAL, None
        else:
            state, reason = JobState.READY, None

        record = AutomationJobRecord(
            workspace_id=payload.workspace_id.strip(),
            requester_id=payload.requester_id.strip(),
            connector_id=payload.connector_id,
            action=payload.action.strip().lower(),
            payload=payload.payload,
            idempotency_key=payload.idempotency_key.strip(),
            requires_human_approval=payload.requires_human_approval,
            human_approved=payload.human_approved,
            state=state,
            max_retries=payload.max_retries,
            blocked_reason=reason,
            error=reason,
        )
        self._jobs[record.id] = record
        self._idempotency[(record.workspace_id, record.idempotency_key)] = record.id
        return record

    def list_jobs(self, workspace_id: str, state: JobState | None = None) -> list[AutomationJobRecord]:
        records = [item for item in self._jobs.values() if item.workspace_id == workspace_id]
        if state is not None:
            records = [item for item in records if item.state == state]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def get_job(self, job_id: UUID, workspace_id: str) -> AutomationJobRecord | None:
        record = self._jobs.get(job_id)
        return record if record and record.workspace_id == workspace_id else None

    def approve_job(self, job_id: UUID, workspace_id: str, payload: JobApproval) -> AutomationJobRecord | None:
        job = self.get_job(job_id, workspace_id)
        if job is None or job.state != JobState.WAITING_APPROVAL:
            return None
        job.human_approved = payload.approved
        job.updated_at = datetime.now(timezone.utc)
        if payload.approved:
            job.state = JobState.READY
            job.error = None
        else:
            job.state = JobState.CANCELLED
            job.error = payload.reason.strip() or f"Denied by {payload.approved_by.strip()}."
        return job

    def dispatch_next(self, workspace_id: str) -> AutomationJobRecord | None:
        candidates = [
            item for item in self._jobs.values()
            if item.workspace_id == workspace_id and item.state == JobState.READY
        ]
        for job in sorted(candidates, key=lambda item: item.created_at):
            connector = self.get_connector(job.connector_id, workspace_id)
            if connector is None or connector.state != ConnectorState.ACTIVE:
                job.state = JobState.BLOCKED
                job.blocked_reason = "Connector unavailable during dispatch."
                job.error = job.blocked_reason
                continue
            if not self._consume_rate_limit(connector):
                continue
            job.state = JobState.RUNNING
            job.started_at = datetime.now(timezone.utc)
            job.updated_at = job.started_at
            job.result = {
                "mode": "dry_run",
                "connector": connector.connector_key,
                "action": job.action,
                "validated": True,
            }
            return job
        return None

    def complete_job(
        self,
        job_id: UUID,
        workspace_id: str,
        payload: JobCompletion,
    ) -> AutomationJobRecord | None:
        job = self.get_job(job_id, workspace_id)
        if job is None or job.state != JobState.RUNNING:
            return None
        now = datetime.now(timezone.utc)
        if payload.success:
            job.state = JobState.COMPLETED
            job.result = {**job.result, **payload.result, "external_side_effect": False}
            job.error = None
            job.completed_at = now
        elif job.retry_count < job.max_retries:
            job.retry_count += 1
            job.state = JobState.READY
            job.error = payload.error.strip() or "Dry-run failed; queued for retry."
        else:
            job.state = JobState.FAILED
            job.error = payload.error.strip() or "Dry-run failed."
            job.completed_at = now
        job.updated_at = now
        return job

    def cancel_job(self, job_id: UUID, workspace_id: str) -> AutomationJobRecord | None:
        job = self.get_job(job_id, workspace_id)
        if job is None or job.state in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}:
            return None
        job.state = JobState.CANCELLED
        job.error = "Cancelled by user."
        job.updated_at = datetime.now(timezone.utc)
        return job

    def _owned_connector(self, connector_id: UUID, workspace_id: str, requester_id: str) -> ConnectorRecord | None:
        connector = self.get_connector(connector_id, workspace_id)
        return connector if connector and connector.owner_id == requester_id else None

    def _consume_rate_limit(self, connector: ConnectorRecord) -> bool:
        now = datetime.now(timezone.utc)
        if now - connector.rate_window_started_at >= timedelta(minutes=1):
            connector.rate_window_started_at = now
            connector.calls_in_current_window = 0
        if connector.calls_in_current_window >= connector.rate_limit_per_minute:
            return False
        connector.calls_in_current_window += 1
        return True

    @staticmethod
    def _normalize(values: list[str]) -> list[str]:
        return sorted({item.strip().lower() for item in values if item.strip()})


automation_runtime_service = AutomationRuntimeService()
