from datetime import datetime, timedelta, timezone

import pytest

from app.audit_compliance.models import (
    AuditEventCreate, ComplianceRuleCreate, EventOutcome, FindingSeverity,
    FindingState, Mutation, ReportCreate, ReportState,
)
from app.audit_compliance.service import AuditComplianceService


def rule(workspace: str = "ws") -> ComplianceRuleCreate:
    return ComplianceRuleCreate(
        workspace_id=workspace,
        owner_id="owner",
        rule_key="denied-approval",
        name="Denied approval activity",
        module="policy-approval",
        action_prefix="approval.",
        prohibited_outcomes=[EventOutcome.DENIED],
        severity=FindingSeverity.HIGH,
    )


def event(workspace: str = "ws", outcome: EventOutcome = EventOutcome.DENIED) -> AuditEventCreate:
    return AuditEventCreate(
        workspace_id=workspace,
        actor_id="operator",
        module="policy-approval",
        action="approval.requested",
        outcome=outcome,
        entity_type="approval",
        entity_id="a-1",
    )


def test_violation_opens_finding_and_reduces_score() -> None:
    service = AuditComplianceService()
    service.create_rule(rule())
    service.record_event(event())
    findings = service.list_findings("ws")
    assert len(findings) == 1
    assert findings[0].severity == FindingSeverity.HIGH
    assert service.metrics("ws").compliance_score == 88.0


def test_finding_lifecycle() -> None:
    service = AuditComplianceService()
    service.create_rule(rule())
    service.record_event(event())
    finding = service.list_findings("ws")[0]
    mutation = Mutation(requester_id="reviewer")
    assert service.mutate_finding(finding.id, "ws", mutation, FindingState.ACKNOWLEDGED).state == FindingState.ACKNOWLEDGED
    assert service.mutate_finding(finding.id, "ws", mutation, FindingState.RESOLVED).state == FindingState.RESOLVED
    assert service.mutate_finding(finding.id, "ws", mutation, FindingState.ARCHIVED).state == FindingState.ARCHIVED


def test_report_lifecycle_and_self_approval_block() -> None:
    service = AuditComplianceService()
    now = datetime.now(timezone.utc)
    report = service.create_report(ReportCreate(
        workspace_id="ws",
        owner_id="owner",
        title="Monthly compliance report",
        period_start=now - timedelta(days=30),
        period_end=now + timedelta(minutes=1),
    ))
    reviewed = service.mutate_report(report.id, "ws", Mutation(requester_id="reviewer"), ReportState.REVIEWED)
    assert reviewed.state == ReportState.REVIEWED
    with pytest.raises(ValueError):
        service.mutate_report(report.id, "ws", Mutation(requester_id="owner"), ReportState.APPROVED)
    approved = service.mutate_report(report.id, "ws", Mutation(requester_id="approver"), ReportState.APPROVED)
    assert approved.state == ReportState.APPROVED


def test_workspace_isolation_and_duplicate_rule_keys() -> None:
    service = AuditComplianceService()
    service.create_rule(rule("a"))
    service.create_rule(rule("b"))
    service.record_event(event("a"))
    assert len(service.list_findings("a")) == 1
    assert service.list_findings("b") == []
    with pytest.raises(ValueError):
        service.create_rule(rule("a"))


def test_failure_threshold_rule() -> None:
    service = AuditComplianceService()
    service.create_rule(ComplianceRuleCreate(
        workspace_id="ws",
        owner_id="owner",
        rule_key="repeated-failures",
        name="Repeated failures",
        module="agent-runtime",
        action_prefix="job.",
        max_failures=2,
        window_minutes=60,
        severity=FindingSeverity.CRITICAL,
    ))
    for _ in range(3):
        service.record_event(AuditEventCreate(
            workspace_id="ws",
            actor_id="agent",
            module="agent-runtime",
            action="job.execute",
            outcome=EventOutcome.FAILURE,
        ))
    assert len(service.list_findings("ws")) == 1
    assert service.metrics("ws").critical_findings == 1


def test_safety_controls() -> None:
    with pytest.raises(ValueError):
        AuditEventCreate(
            workspace_id="ws",
            actor_id="actor",
            module="test",
            action="unsafe",
            outcome=EventOutcome.SUCCESS,
            execute_action=True,
        )
    with pytest.raises(ValueError):
        ComplianceRuleCreate(
            workspace_id="ws",
            owner_id="owner",
            rule_key="unsafe",
            name="Unsafe rule",
            prohibited_outcomes=[EventOutcome.FAILURE],
            automatic_remediation=True,
        )
