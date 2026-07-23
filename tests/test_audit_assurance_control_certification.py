import pytest
from pydantic import ValidationError

from backend.app.modules.audit_assurance_control_certification.models import (
    AssuranceActionRequest,
    AssuranceCreate,
    AssuranceState,
    CertificationAssertion,
    ControlStatus,
    ControlTest,
    RiskDecision,
)
from backend.app.modules.audit_assurance_control_certification.service import AssuranceGovernanceError, AssuranceGovernanceService


def payload(workspace: str = "ws") -> AssuranceCreate:
    return AssuranceCreate(
        workspace_id=workspace,
        source_key="assurance-1",
        compliance_record_id="compliance-1",
        assurance_name="quarterly-control-certification",
        controls=[ControlTest(control_id="c1", control_name="risk approval", owner="risk", status=ControlStatus.EFFECTIVE, evidence_refs=["c1-evidence"])],
        assertions=[CertificationAssertion(assertion_id="a1", title="controls effective", conclusion="controls operated effectively", confidence=0.95, evidence_refs=["a1-evidence"])],
        required_healthy_cycles=2,
        assurance_evidence_refs=["assurance-evidence"],
    )


def act(service, record, action, **kwargs):
    return service.act(record.record_id, record.workspace_id, AssuranceActionRequest(action=action, actor="tester", **kwargs))


def test_full_assurance_lifecycle():
    service = AssuranceGovernanceService()
    record = service.create(payload())
    for action, kwargs in [
        ("prepare-evidence", {}),
        ("assess", {}),
        ("start-testing", {}),
        ("request-review", {}),
        ("approve", {"approval_token": "approval"}),
        ("certify", {"receipt_id": "certificate", "evidence_refs": ["certificate-evidence"]}),
    ]:
        act(service, record, action, **kwargs)
    for index in range(2):
        act(service, record, "record-cycle", receipt_id=f"cycle-{index}", cycle_healthy=True, observed_deficient_controls=0, observed_failed_controls=0)
    act(service, record, "verify", receipt_id="verified")
    assert record.state == AssuranceState.VERIFIED


def test_failed_control_escalates():
    service = AssuranceGovernanceService()
    failed = payload().controls[0].model_copy(update={"status": ControlStatus.FAILED, "severity": 1})
    record = service.create(payload().model_copy(update={"controls": [failed]}))
    act(service, record, "prepare-evidence")
    act(service, record, "assess")
    assert record.state == AssuranceState.ESCALATED


def test_risk_replay_and_isolation():
    service = AssuranceGovernanceService()
    blocked = service.create(payload("blocked").model_copy(update={"source_key": "blocked", "risk_decision": RiskDecision.BLOCK}))
    act(service, blocked, "prepare-evidence")
    assert blocked.state == AssuranceState.BLOCKED

    record = service.create(payload().model_copy(update={"source_key": "second"}))
    for action in ["prepare-evidence", "assess", "start-testing", "request-review"]:
        act(service, record, action)
    act(service, record, "approve", approval_token="token")
    with pytest.raises(AssuranceGovernanceError):
        act(service, record, "certify", receipt_id="receipt")
        act(service, record, "record-cycle", receipt_id="receipt", cycle_healthy=True)
    with pytest.raises(AssuranceGovernanceError):
        service.get(record.record_id, "other")


def test_duplicate_controls_rejected():
    control = payload().controls[0]
    with pytest.raises(ValidationError):
        AssuranceCreate(**payload().model_dump() | {"controls": [control.model_dump(), control.model_dump()]})
