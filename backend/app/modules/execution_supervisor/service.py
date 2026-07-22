from __future__ import annotations

from datetime import datetime, timezone
from secrets import token_urlsafe

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
    """Governed runtime observer. It recommends interventions but never performs them."""

    def __init__(self) -> None:
        self._records: dict[str, SupervisionRecord] = {}
        self._source_index: dict[tuple[str, str], str] = {}
        self._audit: list[AuditEvent] = []
        self._used_intervention_tokens: set[str] = set()
        self._used_receipts: set[str] = set()
        self._policies: dict[str, tuple[int, float, float]] = {}

    def status(self) -> dict[str, object]:
        return {
            "module": "execution-supervisor",
            "version": "21.11",
            "status": "operational",
            "records": len(self._records),
            "safety_boundary": "observe-and-recommend-only",
        }

    def create(self, payload: SupervisionCreate, actor: str = "system") -> SupervisionRecord:
        duplicate = self._source_index.get((payload.workspace_id, payload.source_key))
        if duplicate:
            raise ExecutionSupervisorError(f"duplicate source_key; existing record={duplicate}")

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
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            workflow_id=payload.workflow_id,
            state=state,
            stage_snapshots=payload.stages,
            total_stages=len(payload.stages),
            decision_notes=notes,
        )
        self._records[record.id] = record
        self._source_index[(record.workspace_id, record.source_key)] = record.id
        self._policies[record.id] = (
            payload.stale_heartbeat_seconds,
            payload.minimum_quality_score,
            payload.maximum_error_rate,
        )
        self._append_audit(record, actor, "create", None, record.state.value)
        if state == SupervisionState.OBSERVING:
            self._evaluate(record, payload.stages, actor)
        return record

    def list(self, workspace_id: str) -> list[SupervisionRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> SupervisionRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise ExecutionSupervisorError("record not found")
        return record

    def execute(self, workspace_id: str, record_id: str, action: SupervisionAction) -> SupervisionRecord:
        record = self.get(workspace_id, record_id)
        before = record.state.value

        if action.command == SupervisionCommand.REFRESH:
            if not action.stages:
                raise ExecutionSupervisorError("stage telemetry is required")
            self._evaluate(record, action.stages, action.actor)
            return record

        if action.command == SupervisionCommand.ACKNOWLEDGE:
            if record.state not in {
                SupervisionState.DEGRADED,
                SupervisionState.INCIDENT,
                SupervisionState.HUMAN_REVIEW_REQUIRED,
            }:
                raise ExecutionSupervisorError("record has no acknowledgeable incident")
            token = action.intervention_token or token_urlsafe(24)
            if token in self._used_intervention_tokens:
                raise ExecutionSupervisorError("intervention token replay detected")
            self._used_intervention_tokens.add(token)
            record.intervention_token = token
            record.state = SupervisionState.HUMAN_REVIEW_REQUIRED
        elif action.command in {
            SupervisionCommand.RECOMMEND_PAUSE,
            SupervisionCommand.RECOMMEND_ROLLBACK,
        }:
            if record.state not in {
                SupervisionState.DEGRADED,
                SupervisionState.INCIDENT,
                SupervisionState.HUMAN_REVIEW_REQUIRED,
            }:
                raise ExecutionSupervisorError("intervention recommendation is not valid in current state")
            if not action.downstream_receipt:
                raise ExecutionSupervisorError("downstream receipt is required")
            if action.downstream_receipt in self._used_receipts:
                raise ExecutionSupervisorError("downstream receipt replay detected")
            self._used_receipts.add(action.downstream_receipt)
            record.downstream_receipt = action.downstream_receipt
            record.state = (
                SupervisionState.PAUSE_RECOMMENDED
                if action.command == SupervisionCommand.RECOMMEND_PAUSE
                else SupervisionState.ROLLBACK_RECOMMENDED
            )
        elif action.command == SupervisionCommand.MARK_RECOVERED:
            if record.state not in {
                SupervisionState.DEGRADED,
                SupervisionState.INCIDENT,
                SupervisionState.HUMAN_REVIEW_REQUIRED,
                SupervisionState.PAUSE_RECOMMENDED,
                SupervisionState.ROLLBACK_RECOMMENDED,
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
        record.updated_at = datetime.utcnow()
        self._append_audit(record, action.actor, action.command.value, before, record.state.value)
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def _evaluate(self, record: SupervisionRecord, stages: list[StageTelemetry], actor: str) -> None:
        before = record.state.value
        stale_seconds, minimum_quality, maximum_error = self._policies[record.id]
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
                    stage_key=stage.stage_key,
                    code="stale-heartbeat",
                    severity=IncidentSeverity.CRITICAL,
                    message="Stage heartbeat exceeded the configured freshness threshold.",
                    recommended_action="pause-and-investigate",
                ))
            if timeout_ratio >= 1:
                incidents.append(Incident(
                    stage_key=stage.stage_key,
                    code="timeout-breach",
                    severity=IncidentSeverity.CRITICAL,
                    message="Stage exceeded its execution timeout.",
                    recommended_action="rollback-or-governed-retry",
                ))
            if stage.error_rate > maximum_error:
                incidents.append(Incident(
                    stage_key=stage.stage_key,
                    code="error-rate-breach",
                    severity=IncidentSeverity.CRITICAL,
                    message="Stage error rate exceeded policy.",
                    recommended_action="pause-and-remediate",
                ))
            if stage.output_quality_score < minimum_quality:
                incidents.append(Incident(
                    stage_key=stage.stage_key,
                    code="quality-drift",
                    severity=IncidentSeverity.WARNING,
                    message="Stage output quality fell below policy.",
                    recommended_action="human-review",
                ))
            if not stage.dependency_healthy:
                incidents.append(Incident(
                    stage_key=stage.stage_key,
                    code="dependency-degraded",
                    severity=IncidentSeverity.CRITICAL,
                    message="A required dependency is unhealthy.",
                    recommended_action="pause-dependent-stage",
                ))
            if stage.retry_count > stage.retry_budget:
                incidents.append(Incident(
                    stage_key=stage.stage_key,
                    code="retry-budget-exhausted",
                    severity=IncidentSeverity.CRITICAL,
                    message="Stage exhausted its governed retry budget.",
                    recommended_action="rollback-or-escalate",
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
        record.updated_at = datetime.utcnow()
        self._append_audit(
            record,
            actor,
            "evaluate",
            before,
            record.state.value,
            {
                "health_score": record.health_score,
                "delivery_drift_score": record.delivery_drift_score,
                "incidents": len(incidents),
            },
        )

    def _append_audit(
        self,
        record: SupervisionRecord,
        actor: str,
        action: str,
        from_state: str | None,
        to_state: str,
        details: dict[str, object] | None = None,
    ) -> None:
        self._audit.append(AuditEvent(
            workspace_id=record.workspace_id,
            record_id=record.id,
            action=action,
            actor=actor,
            from_state=from_state,
            to_state=to_state,
            details=details or {},
        ))
