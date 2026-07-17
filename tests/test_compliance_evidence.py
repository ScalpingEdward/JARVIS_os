from datetime import datetime, timedelta, timezone

import pytest

from app.jarvis.compliance_evidence.models import (
    ControlCreate, ControlState, EvidenceCreate, EvidenceState, FindingCreate,
    FindingSeverity, FindingState, Mutation, ReportCreate, ReportState,
)
from app.jarvis.compliance_evidence.service import ComplianceEvidenceService


def control(service: ComplianceEvidenceService, workspace: str = "w1"):
    item = service.create_control(ControlCreate(workspace_id=workspace, owner_id="owner", framework="ISO27001", control_key="A.5.1", title="Policies"))
    return service.set_control_state(item.id, workspace, Mutation(requester_id="owner"), ControlState.ACTIVE)


def test_evidence_report_and_finding_lifecycle():
    service = ComplianceEvidenceService()
    c = control(service)
    evidence = service.create_evidence(EvidenceCreate(workspace_id="w1", owner_id="owner", control_id=c.id, source_module="policy_approval", evidence_type="snapshot", reference="internal://audit/1", checksum="abcdefgh12345678", summary="verified"))
    finding = service.create_finding(FindingCreate(workspace_id="w1", owner_id="owner", control_id=c.id, title="Gap", description="Missing review", severity=FindingSeverity.HIGH, remediation_owner="owner", evidence_ids=[evidence.id]))
    assert service.set_finding_state(finding.id, "w1", Mutation(requester_id="owner", reason="fixed"), FindingState.RESOLVED).state == FindingState.RESOLVED
    report = service.create_report(ReportCreate(workspace_id="w1", owner_id="owner", framework="ISO27001", title="Q3", control_ids=[c.id], period_start=datetime.now(timezone.utc)-timedelta(days=30), period_end=datetime.now(timezone.utc)))
    assert report.coverage_percent == 100.0
    assert report.open_findings == 0
    assert service.set_report_state(report.id, "w1", Mutation(requester_id="owner"), ReportState.APPROVED).state == ReportState.APPROVED
    assert service.set_report_state(report.id, "w1", Mutation(requester_id="owner"), ReportState.FINAL).state == ReportState.FINAL


def test_safety_and_workspace_isolation():
    service = ComplianceEvidenceService()
    c = control(service)
    with pytest.raises(ValueError):
        EvidenceCreate(workspace_id="w1", owner_id="owner", control_id=c.id, source_module="x", evidence_type="x", reference="x", checksum="abcdefgh", raw_secret="secret")
    with pytest.raises(ValueError):
        FindingCreate(workspace_id="w1", owner_id="owner", control_id=c.id, title="x", description="x", severity=FindingSeverity.LOW, remediation_owner="owner", automatic_remediation=True)
    assert service.set_control_state(c.id, "w2", Mutation(requester_id="owner"), ControlState.RETIRED) is None


def test_duplicate_evidence_and_stale_refresh():
    service = ComplianceEvidenceService()
    c = control(service)
    payload = EvidenceCreate(workspace_id="w1", owner_id="owner", control_id=c.id, source_module="x", evidence_type="snapshot", reference="internal://1", checksum="abcdefgh", valid_days=1)
    item = service.create_evidence(payload)
    with pytest.raises(ValueError):
        service.create_evidence(payload)
    item.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert service.list_evidence("w1")[0].state == EvidenceState.STALE
