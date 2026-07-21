from datetime import datetime, timezone
from uuid import UUID

from .models import (
    IncidentFinding,
    ObservabilityExecuteRequest,
    ObservabilityState,
    ProductionObservabilityAudit,
    ProductionObservabilityCreate,
    ProductionObservabilityRecord,
    ProductionObservabilityStatus,
)


class ProductionObservabilityService:
    def __init__(self) -> None:
        self._records: dict[UUID, ProductionObservabilityRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[ProductionObservabilityAudit] = []

    def create(self, payload: ProductionObservabilityCreate) -> ProductionObservabilityRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail, severity, findings, actions = self._evaluate(payload)
        record = ProductionObservabilityRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            severity=severity,
            findings=findings,
            allowed_actions=actions,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: ProductionObservabilityCreate):
        if payload.upstream_risk_brain_blocked:
            return ObservabilityState.BLOCKED, "upstream Risk Brain hard block", "critical", [], []
        if not payload.v20_06_deployment_healthy:
            return ObservabilityState.EVIDENCE_REQUIRED, "v20.06 healthy deployment evidence required", "high", [], []

        snapshot = payload.snapshot
        limits = payload.limits
        findings: list[IncidentFinding] = []
        critical = False

        checks = [
            (not snapshot.health_checks_passed, "health", "critical", "runtime health checks failed"),
            (not snapshot.data_feed_healthy, "data-feed", "critical", "market data feed unhealthy"),
            (not snapshot.broker_connection_healthy, "broker", "critical", "broker connection unhealthy"),
            (not snapshot.database_healthy, "database", "critical", "database unhealthy"),
            (not snapshot.vps_healthy, "vps", "critical", "VPS unhealthy"),
            (not snapshot.queue_healthy, "queue", "high", "queue unhealthy"),
            (snapshot.error_rate_pct > limits.max_error_rate_pct, "error-rate", "high", "error rate above limit"),
            (snapshot.p95_latency_ms > limits.max_p95_latency_ms, "latency", "high", "p95 latency above limit"),
        ]
        for triggered, category, severity, detail in checks:
            if triggered:
                findings.append(IncidentFinding(category=category, severity=severity, detail=detail))
                critical = critical or severity == "critical"
        for alert in snapshot.active_alerts:
            findings.append(IncidentFinding(category="alert", severity="medium", detail=alert))

        if critical:
            return (
                ObservabilityState.HUMAN_REVIEW_REQUIRED,
                "critical production incident requires human review before defensive remediation",
                "critical",
                findings,
                ["start-self-healing", "require-rollback"],
            )
        if findings:
            return (
                ObservabilityState.INCIDENT_OPEN,
                "production degradation detected",
                "high",
                findings,
                ["start-self-healing", "require-rollback"],
            )
        return ObservabilityState.HEALTHY, "production runtime healthy", "none", [], []

    def execute(self, record_id: UUID, workspace_id: str, request: ObservabilityExecuteRequest) -> ProductionObservabilityRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("observability record not found")
        if request.action == "start-self-healing":
            if record.state not in {ObservabilityState.INCIDENT_OPEN, ObservabilityState.HUMAN_REVIEW_REQUIRED, ObservabilityState.DEGRADED}:
                raise ValueError("self-healing unavailable from current state")
            if record.state == ObservabilityState.HUMAN_REVIEW_REQUIRED and not request.human_approved:
                raise ValueError("human approval required for critical incident remediation")
            record.state = ObservabilityState.SELF_HEALING
            record.detail = "defensive self-healing actions started"
        elif request.action == "verify-recovery":
            if record.state != ObservabilityState.SELF_HEALING:
                raise ValueError("recovery verification unavailable")
            record.state = ObservabilityState.RECOVERED if request.recovery_checks_passed else ObservabilityState.ROLLBACK_REQUIRED
            record.detail = "runtime recovered" if request.recovery_checks_passed else "recovery checks failed; rollback required"
        elif request.action == "require-rollback":
            if record.state in {ObservabilityState.HEALTHY, ObservabilityState.RECOVERED, ObservabilityState.ARCHIVED}:
                raise ValueError("rollback unavailable from current state")
            record.state = ObservabilityState.ROLLBACK_REQUIRED
            record.detail = "rollback required by incident coordinator"
        elif request.action == "archive":
            record.state = ObservabilityState.ARCHIVED
            record.detail = "observability record archived"
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> ProductionObservabilityRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[ProductionObservabilityRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ProductionObservabilityStatus:
        records = self.list_records(workspace_id)
        incident_states = {
            ObservabilityState.DEGRADED,
            ObservabilityState.INCIDENT_OPEN,
            ObservabilityState.HUMAN_REVIEW_REQUIRED,
            ObservabilityState.SELF_HEALING,
            ObservabilityState.ROLLBACK_REQUIRED,
        }
        return ProductionObservabilityStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            open_incidents=sum(record.state in incident_states for record in records),
            recovered_records=sum(record.state == ObservabilityState.RECOVERED for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[ProductionObservabilityAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: ProductionObservabilityRecord, actor_id: str, action: str) -> None:
        self._audit.append(ProductionObservabilityAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


production_observability_service = ProductionObservabilityService()
