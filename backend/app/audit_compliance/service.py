from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import (
    AuditComplianceStatus, AuditEventCreate, AuditEventRecord, ComplianceRuleCreate,
    ComplianceRuleRecord, EventOutcome, FindingRecord, FindingSeverity, FindingState,
    MetricsRecord, Mutation, ReportCreate, ReportRecord, ReportState,
)


class AuditComplianceService:
    def __init__(self) -> None:
        self.events: dict[UUID, AuditEventRecord] = {}
        self.rules: dict[UUID, ComplianceRuleRecord] = {}
        self.findings: dict[UUID, FindingRecord] = {}
        self.reports: dict[UUID, ReportRecord] = {}
        self.audit: list[dict] = []

    def status(self) -> AuditComplianceStatus:
        return AuditComplianceStatus()

    def _audit(self, workspace_id: str, action: str, actor_id: str, entity_id: UUID | None = None) -> None:
        self.audit.append({
            "workspace_id": workspace_id,
            "action": action,
            "actor_id": actor_id,
            "entity_id": str(entity_id) if entity_id else None,
            "created_at": datetime.now(timezone.utc),
        })

    def create_rule(self, payload: ComplianceRuleCreate) -> ComplianceRuleRecord:
        duplicate = any(
            item.workspace_id == payload.workspace_id and item.rule_key == payload.rule_key
            for item in self.rules.values()
        )
        if duplicate:
            raise ValueError("compliance rule key already exists in workspace")
        item = ComplianceRuleRecord(**payload.model_dump())
        self.rules[item.id] = item
        self._audit(item.workspace_id, "compliance-rule.created", item.owner_id, item.id)
        return item

    def list_rules(self, workspace_id: str) -> list[ComplianceRuleRecord]:
        return [item for item in self.rules.values() if item.workspace_id == workspace_id]

    def record_event(self, payload: AuditEventCreate) -> AuditEventRecord:
        item = AuditEventRecord(**payload.model_dump())
        self.events[item.id] = item
        self._audit(item.workspace_id, "audit-event.recorded", item.actor_id, item.id)
        self._evaluate(item)
        return item

    def list_events(self, workspace_id: str, module: str | None = None) -> list[AuditEventRecord]:
        return [
            item for item in self.events.values()
            if item.workspace_id == workspace_id and (module is None or item.module == module)
        ]

    def _evaluate(self, event: AuditEventRecord) -> None:
        for rule in self.list_rules(event.workspace_id):
            if not rule.enabled:
                continue
            if rule.module != "*" and rule.module != event.module:
                continue
            if rule.action_prefix and not event.action.startswith(rule.action_prefix):
                continue
            violated = event.outcome in rule.prohibited_outcomes
            if rule.max_failures > 0 and event.outcome == EventOutcome.FAILURE:
                since = event.occurred_at - timedelta(minutes=rule.window_minutes)
                failure_count = sum(
                    candidate.outcome == EventOutcome.FAILURE
                    and candidate.module == event.module
                    and candidate.action == event.action
                    and candidate.occurred_at >= since
                    for candidate in self.list_events(event.workspace_id)
                )
                violated = violated or failure_count > rule.max_failures
            if not violated:
                continue
            duplicate = any(
                finding.workspace_id == event.workspace_id
                and finding.rule_id == rule.id
                and finding.event_id == event.id
                for finding in self.findings.values()
            )
            if duplicate:
                continue
            finding = FindingRecord(
                workspace_id=event.workspace_id,
                rule_id=rule.id,
                event_id=event.id,
                severity=rule.severity,
                title=f"Compliance violation: {rule.name}",
                description=f"{event.module}.{event.action} produced outcome {event.outcome.value}",
            )
            self.findings[finding.id] = finding
            self._audit(event.workspace_id, "finding.opened", event.actor_id, finding.id)

    def list_findings(self, workspace_id: str, state: FindingState | None = None) -> list[FindingRecord]:
        return [
            item for item in self.findings.values()
            if item.workspace_id == workspace_id and (state is None or item.state == state)
        ]

    def mutate_finding(self, finding_id: UUID, workspace_id: str, payload: Mutation, target: FindingState) -> FindingRecord | None:
        item = self.findings.get(finding_id)
        if item is None or item.workspace_id != workspace_id:
            return None
        allowed = {
            FindingState.OPEN: {FindingState.ACKNOWLEDGED, FindingState.RESOLVED, FindingState.ARCHIVED},
            FindingState.ACKNOWLEDGED: {FindingState.RESOLVED, FindingState.ARCHIVED},
            FindingState.RESOLVED: {FindingState.ARCHIVED},
            FindingState.ARCHIVED: set(),
        }
        if target not in allowed[item.state]:
            raise ValueError("invalid finding transition")
        item.state = target
        item.updated_at = datetime.now(timezone.utc)
        if target == FindingState.ACKNOWLEDGED:
            item.acknowledged_by = payload.requester_id
        if target == FindingState.RESOLVED:
            item.resolved_by = payload.requester_id
        self._audit(workspace_id, f"finding.{target.value}", payload.requester_id, item.id)
        return item

    def _score(self, workspace_id: str, start: datetime | None = None, end: datetime | None = None) -> float:
        findings = self.list_findings(workspace_id)
        if start is not None and end is not None:
            findings = [item for item in findings if start <= item.created_at <= end]
        weights = {
            FindingSeverity.LOW: 2,
            FindingSeverity.MEDIUM: 5,
            FindingSeverity.HIGH: 12,
            FindingSeverity.CRITICAL: 25,
        }
        penalty = sum(weights[item.severity] for item in findings if item.state != FindingState.ARCHIVED)
        return max(0.0, round(100.0 - penalty, 2))

    def create_report(self, payload: ReportCreate) -> ReportRecord:
        events = [
            item for item in self.list_events(payload.workspace_id)
            if payload.period_start <= item.occurred_at <= payload.period_end
        ]
        findings = [
            item for item in self.list_findings(payload.workspace_id)
            if payload.period_start <= item.created_at <= payload.period_end
        ]
        item = ReportRecord(
            **payload.model_dump(),
            compliance_score=self._score(payload.workspace_id, payload.period_start, payload.period_end),
            total_events=len(events),
            failed_events=sum(event.outcome in {EventOutcome.FAILURE, EventOutcome.DENIED} for event in events),
            open_findings=sum(finding.state in {FindingState.OPEN, FindingState.ACKNOWLEDGED} for finding in findings),
            critical_findings=sum(
                finding.severity == FindingSeverity.CRITICAL
                and finding.state in {FindingState.OPEN, FindingState.ACKNOWLEDGED}
                for finding in findings
            ),
        )
        self.reports[item.id] = item
        self._audit(item.workspace_id, "report.created", item.owner_id, item.id)
        return item

    def list_reports(self, workspace_id: str) -> list[ReportRecord]:
        return [item for item in self.reports.values() if item.workspace_id == workspace_id]

    def mutate_report(self, report_id: UUID, workspace_id: str, payload: Mutation, target: ReportState) -> ReportRecord | None:
        item = self.reports.get(report_id)
        if item is None or item.workspace_id != workspace_id:
            return None
        allowed = {
            ReportState.DRAFT: {ReportState.REVIEWED, ReportState.ARCHIVED},
            ReportState.REVIEWED: {ReportState.APPROVED, ReportState.ARCHIVED},
            ReportState.APPROVED: {ReportState.ARCHIVED},
            ReportState.ARCHIVED: set(),
        }
        if target not in allowed[item.state]:
            raise ValueError("invalid report transition")
        if target == ReportState.APPROVED and payload.requester_id == item.owner_id:
            raise ValueError("report owner cannot self-approve")
        item.state = target
        item.updated_at = datetime.now(timezone.utc)
        if target == ReportState.REVIEWED:
            item.reviewed_by = payload.requester_id
        if target == ReportState.APPROVED:
            item.approved_by = payload.requester_id
        self._audit(workspace_id, f"report.{target.value}", payload.requester_id, item.id)
        return item

    def metrics(self, workspace_id: str) -> MetricsRecord:
        findings = self.list_findings(workspace_id)
        return MetricsRecord(
            workspace_id=workspace_id,
            audit_events=len(self.list_events(workspace_id)),
            compliance_rules=len(self.list_rules(workspace_id)),
            open_findings=sum(item.state in {FindingState.OPEN, FindingState.ACKNOWLEDGED} for item in findings),
            critical_findings=sum(
                item.severity == FindingSeverity.CRITICAL
                and item.state in {FindingState.OPEN, FindingState.ACKNOWLEDGED}
                for item in findings
            ),
            reports=len(self.list_reports(workspace_id)),
            compliance_score=self._score(workspace_id),
        )

    def list_audit(self, workspace_id: str) -> list[dict]:
        return [item for item in self.audit if item["workspace_id"] == workspace_id]


audit_compliance_service = AuditComplianceService()
