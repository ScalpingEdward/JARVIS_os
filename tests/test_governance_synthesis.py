import pytest
from pydantic import ValidationError

from backend.app.modules.governance_synthesis.models import (
    DirectivePriority,
    ExecutiveDirective,
    GovernanceActionRequest,
    GovernanceDomain,
    GovernanceSignal,
    GovernanceState,
    GovernanceSynthesisCreate,
    RiskDecision,
)
from backend.app.modules.governance_synthesis.service import GovernanceSynthesisError, GovernanceSynthesisService


def payload(workspace: str = "ws") -> GovernanceSynthesisCreate:
    return GovernanceSynthesisCreate(
        workspace_id=workspace,
        source_key="policy-outcomes-1",
        executive_scope="phoenix-control-plane",
        signals=[
            GovernanceSignal(
                signal_id="s1",
                domain=GovernanceDomain.POLICY,
                source_module="policy-evolution",
                source_record_id="pe-1",
                status="promoted",
                severity=30,
                confidence=0.92,
                summary="Policy canary promoted successfully",
                evidence_refs=["ev-s1"],
            ),
            GovernanceSignal(
                signal_id="s2",
                domain=GovernanceDomain.RELIABILITY,
                source_module="self-healing-supervisor",
                source_record_id="sh-1",
                status="healthy",
                severity=20,
                confidence=0.90,
                summary="Recovery remained stable",
                evidence_refs=["ev-s2"],
            ),
        ],
        directives=[
            ExecutiveDirective(
                directive_id="d1",
                title="Maintain controlled recovery policy",
                priority=DirectivePriority.HIGH,
                target_domains=[GovernanceDomain.POLICY, GovernanceDomain.RECOVERY],
                objective="Keep the promoted policy under executive monitoring",
                required_actions=["monitor recovery error rate", "retain rollback readiness"],
                success_criteria=["three healthy monitoring cycles"],
                escalation_conditions=["aggregate risk exceeds limit"],
                evidence_refs=["ev-d1"],
            )
        ],
        governance_evidence_refs=["gov-1"],
    )


def act(service, record, action, **kwargs):
    return service.act(record.record_id, record.workspace_id, GovernanceActionRequest(action=action, actor="executive", **kwargs))


def test_full_executive_directive_lifecycle():
    service = GovernanceSynthesisService()
    record = service.create(payload())
    act(service, record, "prepare-evidence")
    act(service, record, "synthesize")
    act(service, record, "request-executive-review", directive_ids=["d1"])
    act(service, record, "approve", approval_token="approval-1")
    act(service, record, "issue-directive", receipt_id="issue-1")
    for index in range(3):
        act(service, record, "record-monitoring", receipt_id=f"cycle-{index}", monitoring_healthy=True, evidence_refs=[f"e-{index}"])
    act(service, record, "verify", receipt_id="verify-1")
    assert record.state == GovernanceState.VERIFIED
    assert record.selected_directive_ids == ["d1"]


def test_unhealthy_monitoring_escalates():
    service = GovernanceSynthesisService()
    record = service.create(payload())
    for action, kwargs in [
        ("prepare-evidence", {}),
        ("synthesize", {}),
        ("request-executive-review", {"directive_ids": ["d1"]}),
        ("approve", {"approval_token": "a1"}),
        ("issue-directive", {"receipt_id": "i1"}),
    ]:
        act(service, record, action, **kwargs)
    act(service, record, "record-monitoring", receipt_id="bad", monitoring_healthy=False, evidence_refs=["bad-evidence"])
    assert record.state == GovernanceState.ESCALATED


def test_risk_block_and_receipt_replay():
    service = GovernanceSynthesisService()
    blocked = service.create(payload("blocked").model_copy(update={"source_key": "blocked", "risk_decision": RiskDecision.BLOCK}))
    act(service, blocked, "prepare-evidence")
    assert blocked.state == GovernanceState.BLOCKED

    record = service.create(payload().model_copy(update={"source_key": "second"}))
    act(service, record, "prepare-evidence")
    act(service, record, "synthesize")
    act(service, record, "request-executive-review", directive_ids=["d1"])
    act(service, record, "approve", approval_token="unique")
    act(service, record, "issue-directive", receipt_id="same")
    with pytest.raises(GovernanceSynthesisError):
        act(service, record, "record-monitoring", receipt_id="same", monitoring_healthy=True, evidence_refs=["e"])


def test_duplicate_signal_ids_rejected():
    item = payload().signals[0]
    with pytest.raises(ValidationError):
        GovernanceSynthesisCreate(**payload().model_copy(update={"signals": [item, item]}).model_dump())


def test_workspace_isolation():
    service = GovernanceSynthesisService()
    record = service.create(payload())
    with pytest.raises(GovernanceSynthesisError):
        service.get(record.record_id, "other")
