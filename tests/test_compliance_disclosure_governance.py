import pytest
from pydantic import ValidationError

from backend.app.modules.compliance_disclosure_governance.models import (
    ComplianceActionRequest,
    ComplianceCreate,
    ComplianceState,
    DisclosureItem,
    ObligationStatus,
    RegulatoryObligation,
    RiskDecision,
)
from backend.app.modules.compliance_disclosure_governance.service import ComplianceGovernanceError, ComplianceGovernanceService


def payload(workspace: str = "ws") -> ComplianceCreate:
    return ComplianceCreate(
        workspace_id=workspace,
        source_key="compliance-1",
        reporting_record_id="report-1",
        compliance_name="monthly-disclosure",
        obligations=[RegulatoryObligation(obligation_id="o1", jurisdiction="EU", authority="regulator", requirement="file report", status=ObligationStatus.SATISFIED, evidence_refs=["obligation-evidence"])],
        disclosures=[DisclosureItem(disclosure_id="d1", title="Risk disclosure", content_summary="Evidence-backed disclosure", jurisdiction="EU", confidence=0.95, evidence_refs=["disclosure-evidence"])],
        maximum_open_obligations=0,
        required_healthy_cycles=2,
        compliance_evidence_refs=["compliance-evidence"],
    )


def act(service, record, action, **kwargs):
    return service.act(record.record_id, record.workspace_id, ComplianceActionRequest(action=action, actor="tester", **kwargs))


def test_full_compliance_lifecycle():
    service = ComplianceGovernanceService()
    record = service.create(payload())
    for action, kwargs in [
        ("prepare-evidence", {}),
        ("assess", {}),
        ("prepare-disclosure", {}),
        ("request-review", {}),
        ("approve", {"approval_token": "a1"}),
        ("file", {"receipt_id": "r1", "evidence_refs": ["filing"]}),
    ]:
        act(service, record, action, **kwargs)
    for index in range(2):
        act(service, record, "record-cycle", receipt_id=f"c{index}", cycle_healthy=True, observed_open_obligations=0)
    act(service, record, "verify", receipt_id="verify")
    assert record.state == ComplianceState.VERIFIED


def test_breached_obligation_escalates():
    service = ComplianceGovernanceService()
    data = payload().model_copy(update={"obligations": [payload().obligations[0].model_copy(update={"status": ObligationStatus.BREACHED})]})
    record = service.create(data)
    act(service, record, "prepare-evidence")
    act(service, record, "assess")
    assert record.state == ComplianceState.ESCALATED


def test_risk_replay_and_isolation():
    service = ComplianceGovernanceService()
    blocked = service.create(payload("blocked").model_copy(update={"source_key": "blocked", "risk_decision": RiskDecision.BLOCK}))
    act(service, blocked, "prepare-evidence")
    assert blocked.state == ComplianceState.BLOCKED

    record = service.create(payload().model_copy(update={"source_key": "second"}))
    for action in ["prepare-evidence", "assess", "prepare-disclosure", "request-review"]:
        act(service, record, action)
    act(service, record, "approve", approval_token="token")
    with pytest.raises(ComplianceGovernanceError):
        other = service.create(payload("other").model_copy(update={"source_key": "other"}))
        other.state = ComplianceState.REVIEW_REQUIRED
        act(service, other, "approve", approval_token="token")
    with pytest.raises(ComplianceGovernanceError):
        service.get(record.record_id, "other")


def test_duplicate_obligations_rejected():
    obligation = payload().obligations[0]
    with pytest.raises(ValidationError):
        ComplianceCreate(**payload().model_dump() | {"obligations": [obligation.model_dump(), obligation.model_dump()]})
