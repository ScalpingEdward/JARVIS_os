from __future__ import annotations

from datetime import datetime, timezone
from secrets import token_urlsafe

from app.db import SessionLocal
from app.db_models import (
    SupervisionAuditRow,
    SupervisionPolicyRow,
    SupervisionRecordRow,
    SupervisionUsedTokenRow,
)

from .models import (
    AuditEvent,
    Incident,
    IncidentSeverity,
    StageTelemetry,
    SupervisionAction,
    SupervisionCommand,
    SupervisionCreate,
    SupervisionRecord,
    SupervisionState,
)


class ExecutionSupervisorError(RuntimeError):
    pass


class ExecutionSupervisorService:
    """Governed runtime observer. It recommends interventions but never performs them.

    Persisted via the same SessionLocal infrastructure the rest of the
    trading chain already uses -- previously four in-memory structures
    (records, per-record policy thresholds, audit, and intervention-
    token/receipt replay protection), all silently emptied on every
    restart.
    """

    def status(self) -> dict[str, object]:
        with SessionLocal() as session:
            count = session.query(SupervisionRecordRow).count()
        return {
            "module": "execution-supervisor", "version": "21.11", "status": "operational",
            "records": count, "safety_boundary": "observe-and-recommend-only",
        }

    def reset(self) -> None:
        with SessionLocal() as session:
            session.query(SupervisionRecordRow).delete()
            session.query(SupervisionPolicyRow).delete()
            session.query(SupervisionAuditRow).delete()
            session.query(SupervisionUsedTokenRow).delete()
            session.commit()

    def create(self, payload: SupervisionCreate, actor: str = "system") -> SupervisionRecord:
        with SessionLocal() as session:
            existing = (
                session.query(SupervisionRecordRow)
                .filter(
                    SupervisionRecordRow.workspace_id == payload.workspace_id,
                    SupervisionRecordRow.source_key == payload.source_key,
                )
                .first()
            )
            if existing is not None:
                raise ExecutionSupervisorError(f"duplicate source_key; existing record={existing.id}")

            if payload.risk_brain_hard_block:
                state = SupervisionState.BLOCKED
                notes = ["Risk Brain hard block is authoritative."]
            elif not payload.workflow_approved or not payload.v21_10_evidence:
                state = SupervisionState.EVIDENCE_REQUIRED
                notes = ["Approved v21.10 workflow evidence is mandatory."]
            else:
                state = SupervisionState.OBSERVING
                notes = []

            record = SupervisionRecord(
                workspace_id=payload.workspace_id, source_key=payload.source_key,
                workflow_id=payload.workflow_id, state=state,
                stage_snapshots=payload.stages, total_stages=len(payload.stages), decision_notes=notes,
            )
            row = SupervisionRecordRow(
                id=record.id, workspace_id=record.workspace_id, source_key=record.source_key,
                state=state.value, data=record.model_dump_json(),
            )
            session.add(row)
            session.add(SupervisionPolicyRow(
                record_id=record.id, stale_heartbeat_seconds=payload.stale_heartbeat_seconds,
                minimum_quality_score=payload.minimum_quality_score,
                maximum_error_rate=payload.maximum_error_rate,
            ))
            session.add(self._audit_row(record, actor, "create", None, record.state.value))
            if state == SupervisionState.OBSERVING:
                session.flush()  # the policy row must be visible to _evaluate()'s own read-back
                self._evaluate(session, record, payload.stages, actor)
                # _evaluate() mutates `record` in place (state, incidents,
                # health_score, ...) -- the row built above was serialized
                # *before* that, so it must be re-synced now or the stored
                # data would silently disagree with what create() returns.
                row.state = record.state.value
                row.data = record.model_dump_json()
            session.commit()
        return record

    def list(self, workspace_id: str) -> list[SupervisionRecord]:
        with SessionLocal() as session:
            rows = session.query(SupervisionRecordRow).filter(
                SupervisionRecordRow.workspace_id == workspace_id
            ).all()
        return [SupervisionRecord.model_validate_json(r.data) for r in rows]

    def get(self, workspace_id: str, record_id: str) -> SupervisionRecord:
        with SessionLocal() as session:
            row = session.get(SupervisionRecordRow, record_id)
        if row is None or row.workspace_id != workspace_id:
            raise ExecutionSupervisorError("record not found")
        return SupervisionRecord.model_validate_json(row.data)

    def execute(self, workspace_id: str, record_id: str, action: SupervisionAction) -> SupervisionRecord:
        with SessionLocal() as session:
            row = session.get(SupervisionRecordRow, record_id)
            if row is None or row.workspace_id != workspace_id:
                raise ExecutionSupervisorError("record not found")
            record = SupervisionRecord.model_validate_json(row.data)
            before = record.state.value

            if action.command == SupervisionCommand.REFRESH:
                if not action.stages:
                    raise ExecutionSupervisorError("stage telemetry is required")
                self._evaluate(session, record, action.stages, action.actor)
                row.state = record.state.value
                row.data = record.model_dump_json()
                session.commit()
                return record

            if action.command == SupervisionCommand.ACKNOWLEDGE:
                if record.state not in {
                    SupervisionState.DEGRADED, SupervisionState.INCIDENT, SupervisionState.HUMAN_REVIEW_REQUIRED,
                }:
                    raise ExecutionSupervisorError("record has no acknowledgeable incident")
                token = action.intervention_token or token_urlsafe(24)
                self._claim_token_or_raise(session, token, "intervention_token")
                record.intervention_token = token
                record.state = SupervisionState.HUMAN_REVIEW_REQUIRED
            elif action.command in {SupervisionCommand.RECOMMEND_PAUSE, SupervisionCommand.RECOMMEND_ROLLBACK}:
                if record.state not in {
                    SupervisionState.DEGRADED, SupervisionState.INCIDENT, SupervisionState.HUMAN_REVIEW_REQUIRED,
                }:
                    raise ExecutionSupervisorError("intervention recommendation is not valid in current state")
                if not action.downstream_receipt:
                    raise ExecutionSupervisorError("downstream receipt is required")
                self._claim_token_or_raise(session, action.downstream_receipt, "downstream_receipt")
                record.downstream_receipt = action.downstream_receipt
                record.state = (
                    SupervisionState.PAUSE_RECOMMENDED if action.command == SupervisionCommand.RECOMMEND_PAUSE
                    else SupervisionState.ROLLBACK_RECOMMENDED
                )
            elif action.command == SupervisionCommand.MARK_RECOVERED:
                if record.state not in {
                    SupervisionState.DEGRADED, SupervisionState.INCIDENT, SupervisionState.HUMAN_REVIEW_REQUIRED,
                    SupervisionState.PAUSE_RECOMMENDED, SupervisionState.ROLLBACK_RECOMMENDED,
                }:
                    raise ExecutionSupervisorError("record is not recoverable")
                record.state = SupervisionState.RECOVERED
            elif action.command == SupervisionCommand.COMPLETE:
                if record.completed_stages != record.total_stages or record.total_stages == 0:
                    raise ExecutionSupervisorError("all stages must be completed")
                record.state = SupervisionState.COMPLETED
            elif action.command == SupervisionCommand.ARCHIVE:
                record.state = SupervisionState.ARCHIVED

            if action.reason:
                record.decision_notes.append(action.reason)
            record.updated_at = datetime.now(timezone.utc)
            row.state = record.state.value
            row.data = record.model_dump_json()
            session.add(self._audit_row(record, action.actor, action.command.value, before, record.state.value))
            session.commit()
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        with SessionLocal() as session:
            rows = (
                session.query(SupervisionAuditRow)
                .filter(SupervisionAuditRow.workspace_id == workspace_id)
                .order_by(SupervisionAuditRow.created_at)
                .all()
            )
        return [AuditEvent.model_validate_json(r.data) for r in rows]

    def _evaluate(self, session, record: SupervisionRecord, stages: list[StageTelemetry], actor: str) -> None:
        before = record.state.value
        policy = session.get(SupervisionPolicyRow, record.id)
        stale_seconds = policy.stale_heartbeat_seconds
        minimum_quality = policy.minimum_quality_score
        maximum_error = policy.maximum_error_rate
        now = datetime.now(timezone.utc)
        incidents: list[Incident] = []
        completed = 0
        health_components: list[float] = []
        drift_components: list[float] = []

        for stage in stages:
            heartbeat = stage.heartbeat_at
            if heartbeat.tzinfo is None:
                heartbeat = heartbeat.replace(tzinfo=timezone.utc)
            heartbeat_age = max(0.0, (now - heartbeat).total_seconds())
            timeout_ratio = stage.elapsed_seconds / stage.timeout_seconds
            retry_ratio = stage.retry_count / max(1, stage.retry_budget)
            if stage.status.lower() in {"completed", "succeeded", "success"}:
                completed += 1

            score = 100.0
            score -= min(35.0, stage.error_rate * 100)
            score -= max(0.0, minimum_quality - stage.output_quality_score) * 0.6
            score -= min(25.0, max(0.0, timeout_ratio - 0.8) * 50)
            if not stage.dependency_healthy:
                score -= 30
            if heartbeat_age > stale_seconds:
                score -= 35
                incidents.append(Incident(
                    stage_key=stage.stage_key, code="stale-heartbeat", severity=IncidentSeverity.CRITICAL,
                    message="Stage heartbeat exceeded the configured freshness threshold.",
                    recommended_action="pause-and-investigate",
                ))
            if timeout_ratio >= 1:
                incidents.append(Incident(
                    stage_key=stage.stage_key, code="timeout-breach", severity=IncidentSeverity.CRITICAL,
                    message="Stage exceeded its execution timeout.",
                    recommended_action="rollback-or-governed-retry",
                ))
            if stage.error_rate > maximum_error:
                incidents.append(Incident(
                    stage_key=stage.stage_key, code="error-rate-breach", severity=IncidentSeverity.CRITICAL,
                    message="Stage error rate exceeded policy.", recommended_action="pause-and-remediate",
                ))
            if stage.output_quality_score < minimum_quality:
                incidents.append(Incident(
                    stage_key=stage.stage_key, code="quality-drift", severity=IncidentSeverity.WARNING,
                    message="Stage output quality fell below policy.", recommended_action="human-review",
                ))
            if not stage.dependency_healthy:
                incidents.append(Incident(
                    stage_key=stage.stage_key, code="dependency-degraded", severity=IncidentSeverity.CRITICAL,
                    message="A required dependency is unhealthy.", recommended_action="pause-dependent-stage",
                ))
            if stage.retry_count > stage.retry_budget:
                incidents.append(Incident(
                    stage_key=stage.stage_key, code="retry-budget-exhausted", severity=IncidentSeverity.CRITICAL,
                    message="Stage exhausted its governed retry budget.", recommended_action="rollback-or-escalate",
                ))
            health_components.append(max(0.0, score))
            drift_components.append(min(100.0, timeout_ratio * 45 + retry_ratio * 25 + stage.error_rate * 100 * 0.3))

        record.stage_snapshots = stages
        record.total_stages = len(stages)
        record.completed_stages = completed
        record.incidents = incidents
        record.health_score = round(sum(health_components) / max(1, len(health_components)), 2)
        record.delivery_drift_score = round(sum(drift_components) / max(1, len(drift_components)), 2)

        critical = any(item.severity == IncidentSeverity.CRITICAL for item in incidents)
        if completed == len(stages) and not incidents:
            record.state = SupervisionState.COMPLETED
        elif critical:
            record.state = SupervisionState.INCIDENT
        elif incidents or record.health_score < 80 or record.delivery_drift_score > 35:
            record.state = SupervisionState.DEGRADED
        else:
            record.state = SupervisionState.HEALTHY
        record.updated_at = datetime.now(timezone.utc)
        session.add(self._audit_row(
            record, actor, "evaluate", before, record.state.value,
            {
                "health_score": record.health_score,
                "delivery_drift_score": record.delivery_drift_score,
                "incidents": len(incidents),
            },
        ))

    @staticmethod
    def _claim_token_or_raise(session, token: str, kind: str) -> None:
        session.add(SupervisionUsedTokenRow(token=token, kind=kind))
        try:
            session.flush()
        except Exception as exc:
            session.rollback()
            label = "intervention token" if kind == "intervention_token" else "downstream receipt"
            raise ExecutionSupervisorError(f"{label} replay detected") from exc

    @staticmethod
    def _audit_row(
        record: SupervisionRecord, actor: str, action: str, from_state: str | None,
        to_state: str, details: dict[str, object] | None = None,
    ) -> SupervisionAuditRow:
        event = AuditEvent(
            workspace_id=record.workspace_id, record_id=record.id, action=action, actor=actor,
            from_state=from_state, to_state=to_state, details=details or {},
        )
        return SupervisionAuditRow(
            id=event.id, workspace_id=event.workspace_id, created_at=event.created_at,
            data=event.model_dump_json(),
        )
