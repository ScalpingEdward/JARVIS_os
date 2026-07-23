import pytest
from pydantic import ValidationError

from backend.app.modules.enterprise_risk_board_oversight.models import (
    BoardDecision,
    EnterpriseRiskActionRequest,
    EnterpriseRiskCreate,
    EnterpriseRiskItem,
    EnterpriseRiskState,
    RiskDecision,
    RiskLevel,
)
from backend.app.modules.enterprise_risk_board_oversight.service import EnterpriseRiskGovernanceError, EnterpriseRiskGovernanceService


def payload(workspace: str = "ws") -> EnterpriseRiskCreate:
    return EnterpriseRiskCreate(
        workspace_id=workspace,
        source_key="risk-1",
        assurance_record_id="assurance-1",
        register_name="enterprise-risk-register",
        risks=[EnterpriseRiskItem(risk_id="r1", domain="market", owner="cro", level=RiskLevel.MODERATE, likelihood=0.3, impact=0.4, current_exposure=20, risk_appetite_limit=50, control_effectiveness=0.9, evidence_refs=["risk-e1"])],
        board_decisions=[BoardDecision(decision_id="d1", title="Maintain limits", recommendation="Keep current risk limits", confidence=0.95, evidence_refs=["board-e1"])],
        maximum_aggregate_exposure=100,
        maximum_critical_risks=0,
        required_healthy_cycles=2,
        enterprise_risk_evidence_refs=["enterprise-e1"],
    )


def act(service, record, action, **kwargs):
    return service.act(record.record_id, record.workspace_id, EnterpriseRiskActionRequest(action=action, actor="tester", **kwargs))


def test_full_board_oversight_lifecycle():
    service = EnterpriseRiskGovernanceService()
    record = service.create(payload())
    act(service, record, "prepare-evidence")
    act(service, record, "aggregate")
    act(service, record, "prepare-board-pack")
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="a1")
    act(service, record, "present", receipt_id="p1", evidence_refs=["minutes"])
    for index in range(2):
        act(service, record, "record-cycle", receipt_id=f"c{index}", cycle_healthy=True, observed_aggregate_exposure=20, observed_critical_risks=0)
    act(service, record, "verify")
    assert record.state == EnterpriseRiskState.VERIFIED


def test_risk_breach_escalates():
    service = EnterpriseRiskGovernanceService()
    data = payload().model_copy(update={"risks": [payload().risks[0].model_copy(update={"current_exposure": 80})]})
    record = service.create(data)
    act(service, record, "prepare-evidence")
    act(service, record, "aggregate")
    assert record.state == EnterpriseRiskState.ESCALATED


def test_risk_block_replay_and_isolation():
    service = EnterpriseRiskGovernanceService()
    blocked = service.create(payload("blocked").model_copy(update={"source_key": "blocked", "risk_decision": RiskDecision.BLOCK}))
    act(service, blocked, "prepare-evidence")
    assert blocked.state == EnterpriseRiskState.BLOCKED

    record = service.create(payload().model_copy(update={"source_key": "second"}))
    for action in ["prepare-evidence", "aggregate", "prepare-board-pack", "request-review"]:
        act(service, record, action)
    act(service, record, "approve", approval_token="unique")
    with pytest.raises(EnterpriseRiskGovernanceError):
        other = service.create(payload("other").model_copy(update={"source_key": "other"}))
        other.state = EnterpriseRiskState.REVIEW_REQUIRED
        act(service, other, "approve", approval_token="unique")
    with pytest.raises(EnterpriseRiskGovernanceError):
        service.get(record.record_id, "other")


def test_duplicate_risk_ids_rejected():
    risk = payload().risks[0]
    with pytest.raises(ValidationError):
        EnterpriseRiskCreate(**payload().model_dump() | {"risks": [risk.model_dump(), risk.model_dump()]})
