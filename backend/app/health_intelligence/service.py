from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AlertRecord, AlertState, HealthIntelligenceStatus, HealthRuleCreate,
    HealthRuleRecord, HealthSnapshot, HealthState, MetricsRecord, Mutation,
    Severity, TelemetryCreate, TelemetryRecord,
)


class HealthIntelligenceService:
    def __init__(self) -> None:
        self.telemetry: dict[UUID, TelemetryRecord] = {}
        self.rules: dict[UUID, HealthRuleRecord] = {}
        self.alerts: dict[UUID, AlertRecord] = {}
        self.audit: list[dict] = []

    def status(self) -> HealthIntelligenceStatus:
        return HealthIntelligenceStatus()

    def _audit(self, workspace_id: str, action: str, actor_id: str, entity_id: UUID | None = None) -> None:
        self.audit.append({
            "workspace_id": workspace_id,
            "action": action,
            "actor_id": actor_id,
            "entity_id": str(entity_id) if entity_id else None,
            "created_at": datetime.now(timezone.utc),
        })

    def record_telemetry(self, payload: TelemetryCreate) -> TelemetryRecord:
        item = TelemetryRecord(**payload.model_dump())
        self.telemetry[item.id] = item
        self._audit(item.workspace_id, "telemetry.recorded", item.reporter_id, item.id)
        self._evaluate_record(item)
        return item

    def list_telemetry(self, workspace_id: str, target_key: str | None = None) -> list[TelemetryRecord]:
        return [
            item for item in self.telemetry.values()
            if item.workspace_id == workspace_id and (target_key is None or item.target_key == target_key)
        ]

    def create_rule(self, payload: HealthRuleCreate) -> HealthRuleRecord:
        if any(item.workspace_id == payload.workspace_id and item.rule_key == payload.rule_key for item in self.rules.values()):
            raise ValueError("health rule key already exists in workspace")
        item = HealthRuleRecord(**payload.model_dump())
        self.rules[item.id] = item
        self._audit(item.workspace_id, "health-rule.created", item.owner_id, item.id)
        return item

    def list_rules(self, workspace_id: str) -> list[HealthRuleRecord]:
        return [item for item in self.rules.values() if item.workspace_id == workspace_id]

    def _state_for(self, value: float, warning: float, critical: float, higher_is_worse: bool) -> HealthState:
        if higher_is_worse:
            if value >= critical:
                return HealthState.CRITICAL
            if value >= warning:
                return HealthState.WARNING
        else:
            if value <= critical:
                return HealthState.CRITICAL
            if value <= warning:
                return HealthState.WARNING
        return HealthState.HEALTHY

    def _evaluate_record(self, record: TelemetryRecord) -> None:
        matching = [
            rule for rule in self.rules.values()
            if rule.workspace_id == record.workspace_id
            and rule.enabled
            and rule.target_kind == record.target_kind
            and rule.metric_kind == record.metric_kind
        ]
        for rule in matching:
            state = self._state_for(
                record.value,
                rule.warning_threshold,
                rule.critical_threshold,
                rule.higher_is_worse,
            )
            if state not in {HealthState.WARNING, HealthState.CRITICAL}:
                continue
            duplicate = any(
                alert.workspace_id == record.workspace_id
                and alert.target_key == record.target_key
                and alert.rule_id == rule.id
                and alert.state in {AlertState.OPEN, AlertState.ACKNOWLEDGED}
                for alert in self.alerts.values()
            )
            if duplicate:
                continue
            severity = Severity.CRITICAL if state == HealthState.CRITICAL else Severity.WARNING
            alert = AlertRecord(
                workspace_id=record.workspace_id,
                target_kind=record.target_kind,
                target_key=record.target_key,
                metric_kind=record.metric_kind,
                severity=severity,
                title=f"{record.target_key}: {record.metric_kind.value} {state.value}",
                description=f"Observed {record.value}; warning={rule.warning_threshold}; critical={rule.critical_threshold}",
                observed_value=record.value,
                rule_id=rule.id,
            )
            self.alerts[alert.id] = alert
            self._audit(record.workspace_id, "alert.opened", record.reporter_id, alert.id)

    def snapshots(self, workspace_id: str) -> list[HealthSnapshot]:
        latest: dict[tuple, TelemetryRecord] = {}
        for item in self.list_telemetry(workspace_id):
            key = (item.target_kind, item.target_key, item.metric_kind)
            previous = latest.get(key)
            if previous is None or item.observed_at > previous.observed_at:
                latest[key] = item
        result: list[HealthSnapshot] = []
        for item in latest.values():
            rules = [
                rule for rule in self.list_rules(workspace_id)
                if rule.enabled and rule.target_kind == item.target_kind and rule.metric_kind == item.metric_kind
            ]
            if not rules:
                state = HealthState.UNKNOWN
                reason = "no-active-rule"
            else:
                states = [self._state_for(item.value, r.warning_threshold, r.critical_threshold, r.higher_is_worse) for r in rules]
                state = HealthState.CRITICAL if HealthState.CRITICAL in states else HealthState.WARNING if HealthState.WARNING in states else HealthState.HEALTHY
                reason = "threshold-evaluation"
            result.append(HealthSnapshot(
                workspace_id=workspace_id,
                target_kind=item.target_kind,
                target_key=item.target_key,
                state=state,
                metric_kind=item.metric_kind,
                value=item.value,
                reason=reason,
                observed_at=item.observed_at,
            ))
        return result

    def list_alerts(self, workspace_id: str, state: AlertState | None = None) -> list[AlertRecord]:
        return [
            item for item in self.alerts.values()
            if item.workspace_id == workspace_id and (state is None or item.state == state)
        ]

    def mutate_alert(self, alert_id: UUID, workspace_id: str, payload: Mutation, target: AlertState) -> AlertRecord | None:
        item = self.alerts.get(alert_id)
        if item is None or item.workspace_id != workspace_id:
            return None
        allowed = {
            AlertState.OPEN: {AlertState.ACKNOWLEDGED, AlertState.RESOLVED, AlertState.ARCHIVED},
            AlertState.ACKNOWLEDGED: {AlertState.RESOLVED, AlertState.ARCHIVED},
            AlertState.RESOLVED: {AlertState.ARCHIVED},
            AlertState.ARCHIVED: set(),
        }
        if target not in allowed[item.state]:
            raise ValueError("invalid alert transition")
        item.state = target
        item.updated_at = datetime.now(timezone.utc)
        if target == AlertState.ACKNOWLEDGED:
            item.acknowledged_by = payload.requester_id
        if target == AlertState.RESOLVED:
            item.resolved_by = payload.requester_id
        self._audit(workspace_id, f"alert.{target.value}", payload.requester_id, item.id)
        return item

    def metrics(self, workspace_id: str) -> MetricsRecord:
        telemetry = self.list_telemetry(workspace_id)
        alerts = self.list_alerts(workspace_id)
        targets = {(x.target_kind, x.target_key) for x in telemetry}
        return MetricsRecord(
            workspace_id=workspace_id,
            telemetry_records=len(telemetry),
            health_rules=len(self.list_rules(workspace_id)),
            open_alerts=sum(x.state in {AlertState.OPEN, AlertState.ACKNOWLEDGED} for x in alerts),
            critical_alerts=sum(x.severity == Severity.CRITICAL and x.state in {AlertState.OPEN, AlertState.ACKNOWLEDGED} for x in alerts),
            monitored_targets=len(targets),
        )

    def list_audit(self, workspace_id: str) -> list[dict]:
        return [item for item in self.audit if item["workspace_id"] == workspace_id]


health_intelligence_service = HealthIntelligenceService()
