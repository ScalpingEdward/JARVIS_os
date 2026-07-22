import pytest
from pydantic import ValidationError

from backend.app.modules.continuous_assurance_attestation.models import (
    AssuranceActionRequest,
    AssuranceAssessmentCreate,
    AssuranceState,
    PolicyControl,
    RemediationControl,
    RiskDecision,
)
from backend.app.modules.continuous_assurance_attestation.service import (
    ContinuousAssuranceError,
    ContinuousAssuranceService,
)


def payload(source_key: str = "source-1", compliant: bool = True) -> AssuranceAssessmentCreate:
    return AssuranceAssessmentCreate(
        workspace_id="workspace-a",
        source_key=source_key,
        trust_assessment_id="trust-32",
        policy_version="policy-7",
        configuration_version="config-44",
        runtime_ids=["runtime-1"],
        controls=[
            PolicyControl(control_id="c1", policy_id="p1", description="risk gate", weight=0.6, expected_value="enabled", observed_value="enabled" if compliant else "disabled", evidence_ref="e1", compliant=compliant),
            PolicyControl(control_id="c2", policy_id="p2", description="audit", weight=0.4, expected_value="enabled", observed_value="enabled", evidence_ref="e2", compliant=True),
        ],
        remediations=[] if compliant else [RemediationControl(remediation_id="r1", control_id="c1", action="enable risk gate", owner="runtime", expected_risk_reduction=0.9)],
        trust_evidence_refs=["trust-evidence"],
        runtime_evidence_refs=["runtime-evidence"],
    )


def action(name: str, **kwargs) -> AssuranceActionRequest:
    return AssuranceActionRequest(action=name, actor="operator", **kwargs)


def test_compliant_attestation_lifecycle() -> None:
    service = ContinuousAssuranceService()
    record = service.create(payload())
    record = service.act(record.record_id, "workspace-a", action("evaluate"))
    assert record.assurance_score == 100
    record = service.act(record.record_id, "workspace-a", action("request-review"))
    record = service.act(record.record_id, "workspace-a", action("approve", approval_token="approval-1"))
    record = service.act(record.record_id, "workspace-a", action("attest", attestation_digest="digest-123456"))
    assert record.state == AssuranceState.ATTESTED
    assert len(service.audit("workspace-a")) == 5


def test_remediation_lifecycle() -> None:
    service = ContinuousAssuranceService()
    record = service.create(payload(compliant=False))
    record = service.act(record.record_id, "workspace-a", action("evaluate"))
    assert record.required_failure_count == 1
    record = service.act(record.record_id, "workspace-a", action("request-review"))
    record = service.act(record.record_id, "workspace-a", action("approve", approval_token="approval-2"))
    record = service.act(record.record_id, "workspace-a", action("queue-remediation", receipt_id="queue-1"))
    record = service.act(record.record_id, "workspace-a", action("complete-remediation", receipt_id="apply-1", applied_remediation_ids=["r1"]))
    record = service.act(record.record_id, "workspace-a", action("verify", receipt_id="verify-1", verification_evidence_refs=["verification"] ))
    assert record.state == AssuranceState.VERIFIED


def test_risk_block_is_authoritative() -> None:
    service = ContinuousAssuranceService()
    blocked = payload().model_copy(update={"source_key": "blocked", "risk_decision": RiskDecision.BLOCK})
    record = service.create(blocked)
    with pytest.raises(ContinuousAssuranceError, match="hard block"):
        service.act(record.record_id, "workspace-a", action("evaluate"))


def test_replay_and_workspace_isolation() -> None:
    service = ContinuousAssuranceService()
    first = service.create(payload("one"))
    second = service.create(payload("two"))
    for record in (first, second):
        service.act(record.record_id, "workspace-a", action("evaluate"))
        service.act(record.record_id, "workspace-a", action("request-review"))
    service.act(first.record_id, "workspace-a", action("approve", approval_token="same-token"))
    with pytest.raises(ContinuousAssuranceError, match="replay"):
        service.act(second.record_id, "workspace-a", action("approve", approval_token="same-token"))
    with pytest.raises(ContinuousAssuranceError, match="not found"):
        service.get(first.record_id, "workspace-b")


def test_integrity_validation() -> None:
    with pytest.raises(ValidationError, match="exactly 1.0"):
        payload().model_copy(update={"controls": [PolicyControl(control_id="x", policy_id="p", description="x", weight=0.5, expected_value="1", observed_value="1", evidence_ref="e", compliant=True)]}).model_dump()

    with pytest.raises(ValidationError, match="known control"):
        AssuranceAssessmentCreate(
            **payload().model_dump(exclude={"remediations"}),
            remediations=[RemediationControl(remediation_id="bad", control_id="missing", action="fix", owner="ops", expected_risk_reduction=0.5)],
        )
