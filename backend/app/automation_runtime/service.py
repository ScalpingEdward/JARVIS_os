from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.db import SessionLocal
from app.db_models import AutomationConnectorRow, AutomationJobRow
from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError

from .models import (
    AutomationJobCreate,
    AutomationJobRecord,
    ConnectorMutation,
    ConnectorRecord,
    ConnectorRegister,
    ConnectorState,
    ConnectorType,
    JobApproval,
    JobCompletion,
    JobState,
    RuntimeStatus,
)


class AutomationRuntimeService:
    #: Connector types allowed a real (non-dry-run) job. Everything else is
    #: refused at create_job(), regardless of connector state or approval --
    #: this is the one place that decision is enforced; nothing downstream
    #: (dispatch_next, execute_telegram_job) re-derives or can widen it.
    REAL_EXECUTION_CONNECTOR_TYPES = frozenset({ConnectorType.TELEGRAM})

    def __init__(self, telegram_client: TelegramDeliveryClient | None = None) -> None:
        self._telegram_client = telegram_client or TelegramDeliveryClient()

    def reset(self) -> None:
        """Needed now that storage is real and shared rather than
        fresh-per-instance in-memory."""
        with SessionLocal() as session:
            session.query(AutomationConnectorRow).delete()
            session.query(AutomationJobRow).delete()
            session.commit()

    def status(self) -> RuntimeStatus:
        with SessionLocal() as session:
            connectors = [ConnectorRecord.model_validate_json(r.data) for r in session.query(AutomationConnectorRow).all()]
            jobs = [AutomationJobRecord.model_validate_json(r.data) for r in session.query(AutomationJobRow).all()]
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
        connector_key = payload.connector_key.strip().lower()
        with SessionLocal() as session:
            duplicate = (
                session.query(AutomationConnectorRow)
                .filter(
                    AutomationConnectorRow.workspace_id == payload.workspace_id.strip(),
                    AutomationConnectorRow.connector_key == connector_key,
                )
                .first()
            )
            if duplicate is not None:
                raise ValueError("connector key already exists in workspace")
            record = ConnectorRecord(
                workspace_id=payload.workspace_id.strip(),
                owner_id=payload.owner_id.strip(),
                connector_key=connector_key,
                connector_type=payload.connector_type,
                display_name=payload.display_name.strip(),
                capabilities=self._normalize(payload.capabilities),
                actions=self._normalize(payload.actions),
                rate_limit_per_minute=payload.rate_limit_per_minute,
                supports_dry_run=payload.supports_dry_run,
            )
            session.add(AutomationConnectorRow(
                id=str(record.id), workspace_id=record.workspace_id, connector_key=record.connector_key,
                data=record.model_dump_json(),
            ))
            session.commit()
        return record

    def list_connectors(self, workspace_id: str) -> list[ConnectorRecord]:
        with SessionLocal() as session:
            rows = session.query(AutomationConnectorRow).filter(
                AutomationConnectorRow.workspace_id == workspace_id
            ).all()
        records = [ConnectorRecord.model_validate_json(r.data) for r in rows]
        return sorted(records, key=lambda item: item.created_at)

    def get_connector(self, connector_id: UUID, workspace_id: str) -> ConnectorRecord | None:
        with SessionLocal() as session:
            row = session.get(AutomationConnectorRow, str(connector_id))
        if row is None or row.workspace_id != workspace_id:
            return None
        return ConnectorRecord.model_validate_json(row.data)

    def _save_connector(self, session, connector: ConnectorRecord) -> None:
        row = session.get(AutomationConnectorRow, str(connector.id))
        row.data = connector.model_dump_json()

    def activate_connector(
        self, connector_id: UUID, workspace_id: str, requester_id: str, payload: ConnectorMutation,
    ) -> ConnectorRecord | None:
        with SessionLocal() as session:
            connector = self._owned_connector_in_session(session, connector_id, workspace_id, requester_id)
            if connector is None:
                return None
            connector.state = ConnectorState.ACTIVE
            connector.health_message = payload.reason.strip() or "Active"
            connector.updated_at = datetime.now(timezone.utc)
            self._save_connector(session, connector)
            session.commit()
        return connector

    def disable_connector(
        self, connector_id: UUID, workspace_id: str, requester_id: str, payload: ConnectorMutation,
    ) -> ConnectorRecord | None:
        with SessionLocal() as session:
            connector = self._owned_connector_in_session(session, connector_id, workspace_id, requester_id)
            if connector is None:
                return None
            connector.state = ConnectorState.DISABLED
            connector.health_message = payload.reason.strip() or "Disabled"
            connector.updated_at = datetime.now(timezone.utc)
            self._save_connector(session, connector)
            session.commit()
        return connector

    def heartbeat(self, connector_id: UUID, workspace_id: str, healthy: bool, message: str) -> ConnectorRecord | None:
        with SessionLocal() as session:
            row = session.get(AutomationConnectorRow, str(connector_id))
            if row is None or row.workspace_id != workspace_id:
                return None
            connector = ConnectorRecord.model_validate_json(row.data)
            connector.last_heartbeat_at = datetime.now(timezone.utc)
            connector.health_message = message.strip() or ("Healthy" if healthy else "Degraded")
            if connector.state != ConnectorState.DISABLED:
                connector.state = ConnectorState.ACTIVE if healthy else ConnectorState.DEGRADED
            connector.updated_at = datetime.now(timezone.utc)
            row.data = connector.model_dump_json()
            session.commit()
        return connector

    def create_job(self, payload: AutomationJobCreate) -> AutomationJobRecord:
        workspace_id = payload.workspace_id.strip()
        idempotency_key = payload.idempotency_key.strip()
        with SessionLocal() as session:
            existing = (
                session.query(AutomationJobRow)
                .filter(
                    AutomationJobRow.workspace_id == workspace_id,
                    AutomationJobRow.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing is not None:
                return AutomationJobRecord.model_validate_json(existing.data)

            connector_row = session.get(AutomationConnectorRow, str(payload.connector_id))
            connector = (
                ConnectorRecord.model_validate_json(connector_row.data)
                if connector_row is not None and connector_row.workspace_id == workspace_id
                else None
            )
            if connector is None:
                state, reason = JobState.BLOCKED, "Connector not found in workspace."
            elif connector.state != ConnectorState.ACTIVE:
                state, reason = JobState.BLOCKED, "Connector is not active."
            elif payload.action.strip().lower() not in connector.actions:
                state, reason = JobState.BLOCKED, "Action is not declared by connector."
            elif payload.dry_run and not connector.supports_dry_run:
                state, reason = JobState.BLOCKED, "Connector does not support dry-run execution."
            elif payload.external_action and connector.connector_type not in self.REAL_EXECUTION_CONNECTOR_TYPES:
                state, reason = JobState.BLOCKED, (
                    f"Real execution is only permitted for "
                    f"{', '.join(sorted(t.value for t in self.REAL_EXECUTION_CONNECTOR_TYPES))} "
                    f"connectors; {connector.connector_type.value} remains dry-run only."
                )
            elif payload.requires_human_approval and not payload.human_approved:
                state, reason = JobState.WAITING_APPROVAL, None
            else:
                state, reason = JobState.READY, None

            record = AutomationJobRecord(
                workspace_id=workspace_id, requester_id=payload.requester_id.strip(),
                connector_id=payload.connector_id, action=payload.action.strip().lower(),
                payload=payload.payload, idempotency_key=idempotency_key, dry_run=payload.dry_run,
                external_action=payload.external_action, requires_human_approval=payload.requires_human_approval,
                human_approved=payload.human_approved, state=state, max_retries=payload.max_retries,
                blocked_reason=reason, error=reason,
            )
            session.add(AutomationJobRow(
                id=str(record.id), workspace_id=record.workspace_id, idempotency_key=record.idempotency_key,
                state=state.value, data=record.model_dump_json(),
            ))
            session.commit()
        return record

    def list_jobs(self, workspace_id: str, state: JobState | None = None) -> list[AutomationJobRecord]:
        with SessionLocal() as session:
            query = session.query(AutomationJobRow).filter(AutomationJobRow.workspace_id == workspace_id)
            if state is not None:
                query = query.filter(AutomationJobRow.state == state.value)
            rows = query.all()
        records = [AutomationJobRecord.model_validate_json(r.data) for r in rows]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def get_job(self, job_id: UUID, workspace_id: str) -> AutomationJobRecord | None:
        with SessionLocal() as session:
            row = session.get(AutomationJobRow, str(job_id))
        if row is None or row.workspace_id != workspace_id:
            return None
        return AutomationJobRecord.model_validate_json(row.data)

    def _save_job(self, session, job: AutomationJobRecord) -> None:
        row = session.get(AutomationJobRow, str(job.id))
        row.state = job.state.value
        row.data = job.model_dump_json()

    def approve_job(self, job_id: UUID, workspace_id: str, payload: JobApproval) -> AutomationJobRecord | None:
        with SessionLocal() as session:
            row = session.get(AutomationJobRow, str(job_id))
            if row is None or row.workspace_id != workspace_id:
                return None
            job = AutomationJobRecord.model_validate_json(row.data)
            if job.state != JobState.WAITING_APPROVAL:
                return None
            job.human_approved = payload.approved
            job.updated_at = datetime.now(timezone.utc)
            if payload.approved:
                job.state = JobState.READY
                job.error = None
            else:
                job.state = JobState.CANCELLED
                job.error = payload.reason.strip() or f"Denied by {payload.approved_by.strip()}."
            self._save_job(session, job)
            session.commit()
        return job

    def dispatch_next(self, workspace_id: str) -> AutomationJobRecord | None:
        with SessionLocal() as session:
            candidate_rows = (
                session.query(AutomationJobRow)
                .filter(AutomationJobRow.workspace_id == workspace_id, AutomationJobRow.state == JobState.READY.value)
                .all()
            )
            candidates = [(r, AutomationJobRecord.model_validate_json(r.data)) for r in candidate_rows]
            for row, job in sorted(candidates, key=lambda pair: pair[1].created_at):
                connector_row = session.get(AutomationConnectorRow, str(job.connector_id))
                connector = (
                    ConnectorRecord.model_validate_json(connector_row.data)
                    if connector_row is not None and connector_row.workspace_id == workspace_id
                    else None
                )
                if connector is None or connector.state != ConnectorState.ACTIVE:
                    job.state = JobState.BLOCKED
                    job.blocked_reason = "Connector unavailable during dispatch."
                    job.error = job.blocked_reason
                    self._save_job(session, job)
                    session.commit()
                    continue
                if not self._consume_rate_limit(connector):
                    self._save_connector(session, connector)
                    session.commit()
                    continue
                self._save_connector(session, connector)
                job.state = JobState.RUNNING
                job.started_at = datetime.now(timezone.utc)
                job.updated_at = job.started_at
                if job.dry_run:
                    job.result = {
                        "mode": "dry_run", "connector": connector.connector_key,
                        "action": job.action, "validated": True,
                    }
                # A real job is claimed here but not yet performed -- nothing
                # simulates a result for it. execute_telegram_job() (or, for a
                # future connector type, its equivalent) does the actual send
                # and calls complete_job() itself with the real outcome.
                self._save_job(session, job)
                session.commit()
                return job
            session.commit()
        return None

    def complete_job(self, job_id: UUID, workspace_id: str, payload: JobCompletion) -> AutomationJobRecord | None:
        with SessionLocal() as session:
            row = session.get(AutomationJobRow, str(job_id))
            if row is None or row.workspace_id != workspace_id:
                return None
            job = AutomationJobRecord.model_validate_json(row.data)
            if job.state != JobState.RUNNING:
                return None
            now = datetime.now(timezone.utc)
            if payload.success:
                job.state = JobState.COMPLETED
                # Reflects what this job actually was, not a hardcoded constant:
                # a real (external_action=True) job had a real side effect if it
                # reached here successfully; a dry run never did.
                job.result = {**job.result, **payload.result, "external_side_effect": job.external_action}
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
            self._save_job(session, job)
            session.commit()
        return job

    def execute_telegram_job(self, job_id: UUID, workspace_id: str) -> AutomationJobRecord | None:
        """Performs the one real, currently-permitted external action:
        sending a Telegram message for a claimed, real (dry_run=False)
        Telegram-connector job. Everything before this point (create_job's
        connector-type gate, dispatch_next's claim) already established that
        this is allowed and this specific job is real -- this method still
        re-checks both rather than trusting that, since a job record is a
        long-lived value a caller could otherwise pass in from anywhere.

        Expects job.payload to carry 'title' and/or 'message' -- both
        optional, matching TelegramDeliveryClient.send()'s own shape; an
        empty payload sends an empty-titled message rather than refusing,
        since the payload's exact contents are the caller's business, not
        this method's to validate beyond what sending actually requires.
        """
        job = self.get_job(job_id, workspace_id)
        if job is None:
            return None
        if job.state != JobState.RUNNING:
            raise ValueError(f"Job {job_id} is {job.state.value}, not running -- nothing to execute")
        if job.dry_run or not job.external_action:
            raise ValueError(f"Job {job_id} is a dry run, not a real action -- nothing to execute")

        connector = self.get_connector(job.connector_id, workspace_id)
        if connector is None or connector.connector_type != ConnectorType.TELEGRAM:
            raise ValueError(
                f"Job {job_id}'s connector is not a Telegram connector -- "
                "execute_telegram_job cannot act on it"
            )

        title = str(job.payload.get("title", ""))
        message = str(job.payload.get("message", ""))
        try:
            self._telegram_client.send(title, message)
        except TelegramDeliveryError as exc:
            return self.complete_job(job_id, workspace_id, JobCompletion(success=False, error=str(exc)))

        return self.complete_job(
            job_id, workspace_id,
            JobCompletion(success=True, result={"channel": "telegram", "title": title}),
        )

    def cancel_job(self, job_id: UUID, workspace_id: str) -> AutomationJobRecord | None:
        with SessionLocal() as session:
            row = session.get(AutomationJobRow, str(job_id))
            if row is None or row.workspace_id != workspace_id:
                return None
            job = AutomationJobRecord.model_validate_json(row.data)
            if job.state in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}:
                return None
            job.state = JobState.CANCELLED
            job.error = "Cancelled by user."
            job.updated_at = datetime.now(timezone.utc)
            self._save_job(session, job)
            session.commit()
        return job

    def _owned_connector_in_session(
        self, session, connector_id: UUID, workspace_id: str, requester_id: str,
    ) -> ConnectorRecord | None:
        row = session.get(AutomationConnectorRow, str(connector_id))
        if row is None or row.workspace_id != workspace_id:
            return None
        connector = ConnectorRecord.model_validate_json(row.data)
        return connector if connector.owner_id == requester_id else None

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
