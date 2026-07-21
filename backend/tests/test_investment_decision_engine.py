import pytest

from app.modules.investment_decision_engine.models import (
    InvestmentDecisionCreate,
    InvestmentDecisionExecute,
    InvestmentDecisionState,
    InvestmentOption,
)
from app.modules.investment_decision_engine.service import InvestmentDecisionError, InvestmentDecisionService


def payload(workspace: str = "ws-a", source_key: str = "risk-1") -> InvestmentDecisionCreate:
    return InvestmentDecisionCreate(
        workspace_id=workspace,
        source_risk_register_id="risk-register-1",
        source_key=source_key,
        available_capital=100_000,
        minimum_expected_roi=0.10,
        maximum_residual_risk=60,
        strategic_constraints=["protect runway", "preserve reversibility"],
        evidence_refs=["v21.07:risk-register-1"],
        options=[
            InvestmentOption(
                option_id="alpha",
                name="Strategic platform build",
                required_capital=40_000,
                expected_value=100_000,
                probability_of_success=0.8,
                time_to_value_months=6,
                strategic_alignment=90,
                reversibility=75,
                residual_risk_score=25,
                evidence_refs=["evidence:alpha"],
            ),
            InvestmentOption(
                option_id="beta",
                name="High-risk expansion",
                required_capital=80_000,
                expected_value=130_000,
                probability_of_success=0.55,
                time_to_value_months=15,
                strategic_alignment=65,
                reversibility=25,
                residual_risk_score=85,
                evidence_refs=["evidence:beta"],
            ),
        ],
    )


def test_analyze_approve_and_issue() -> None:
    service = InvestmentDecisionService()
    record = service.create(payload())
    analyzed = service.execute("ws-a", record.record_id, InvestmentDecisionExecute(action="analyze", actor_id="analyst"))
    assert analyzed.selected_option_ids == ["alpha"]
    assert analyzed.state == InvestmentDecisionState.HUMAN_REVIEW_REQUIRED

    # Remove the critical option to create a clean approval path.
    clean = payload(source_key="risk-2")
    clean.options = [clean.options[0]]
    record2 = service.create(clean)
    ready = service.execute("ws-a", record2.record_id, InvestmentDecisionExecute(action="analyze", actor_id="analyst"))
    assert ready.state == InvestmentDecisionState.DECISION_READY
    assert ready.approval_token

    approved = service.execute(
        "ws-a",
        record2.record_id,
        InvestmentDecisionExecute(action="approve", actor_id="executive", approval_token=ready.approval_token),
    )
    assert approved.state == InvestmentDecisionState.APPROVED

    issued = service.execute(
        "ws-a",
        record2.record_id,
        InvestmentDecisionExecute(action="issue", actor_id="executive", downstream_receipt="execution-plan-1"),
    )
    assert issued.state == InvestmentDecisionState.ISSUED_TO_EXECUTION_PLANNING


def test_hard_block_and_missing_evidence_fail_closed() -> None:
    service = InvestmentDecisionService()
    blocked_payload = payload()
    blocked_payload.risk_brain_hard_block = True
    blocked = service.create(blocked_payload)
    assert blocked.state == InvestmentDecisionState.BLOCKED
    with pytest.raises(InvestmentDecisionError):
        service.execute("ws-a", blocked.record_id, InvestmentDecisionExecute(action="analyze", actor_id="analyst"))

    missing = payload(source_key="missing")
    missing.options[0].evidence_refs = []
    evidence_record = service.create(missing)
    assert evidence_record.state == InvestmentDecisionState.EVIDENCE_REQUIRED


def test_duplicate_source_workspace_isolation_and_receipt_replay() -> None:
    service = InvestmentDecisionService()
    service.create(payload())
    with pytest.raises(InvestmentDecisionError):
        service.create(payload())

    other = service.create(payload(workspace="ws-b"))
    with pytest.raises(InvestmentDecisionError):
        service.get("ws-a", other.record_id)

    clean = payload(source_key="clean")
    clean.options = [clean.options[0]]
    first = service.create(clean)
    ready = service.execute("ws-a", first.record_id, InvestmentDecisionExecute(action="analyze", actor_id="a"))
    service.execute("ws-a", first.record_id, InvestmentDecisionExecute(action="approve", actor_id="e", approval_token=ready.approval_token))
    service.execute("ws-a", first.record_id, InvestmentDecisionExecute(action="issue", actor_id="e", downstream_receipt="receipt-1"))

    second_payload = payload(source_key="clean-2")
    second_payload.options = [second_payload.options[0]]
    second = service.create(second_payload)
    ready2 = service.execute("ws-a", second.record_id, InvestmentDecisionExecute(action="analyze", actor_id="a"))
    service.execute("ws-a", second.record_id, InvestmentDecisionExecute(action="approve", actor_id="e", approval_token=ready2.approval_token))
    with pytest.raises(InvestmentDecisionError):
        service.execute("ws-a", second.record_id, InvestmentDecisionExecute(action="issue", actor_id="e", downstream_receipt="receipt-1"))
