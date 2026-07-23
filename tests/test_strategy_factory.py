import pytest
from pydantic import ValidationError

from backend.app.phoenix.v21_54_strategy_factory.models import (
    RiskDecision,
    StrategyFactoryActionRequest,
    StrategyFactoryCreate,
    StrategyFactoryState,
)
from backend.app.phoenix.v21_54_strategy_factory.service import (
    StrategyFactoryError,
    StrategyFactoryService,
)


def payload(**overrides):
    data = {
        "workspace_id": "ws-a",
        "source_key": "factory-001",
        "portfolio_record_id": "portfolio-001",
        "program_name": "XAU alpha factory",
        "candidates": [
            {
                "candidate_id": "alpha-1",
                "name": "London sweep continuation",
                "owner": "strategy-brain",
                "market": "XAUUSD",
                "timeframe": "M15",
                "hypothesis": "Liquidity sweep followed by displacement produces persistent alpha.",
                "expected_alpha": 0.12,
                "expected_sharpe": 1.8,
                "maximum_drawdown": 0.08,
                "capacity_score": 0.9,
                "robustness_score": 0.91,
                "confidence": 0.93,
                "evidence_refs": ["research://alpha-1"],
            },
            {
                "candidate_id": "alpha-2",
                "name": "NY reversal",
                "owner": "strategy-brain",
                "market": "XAUUSD",
                "timeframe": "M5",
                "hypothesis": "Late-session exhaustion creates mean-reversion alpha.",
                "expected_alpha": 0.07,
                "expected_sharpe": 1.2,
                "maximum_drawdown": 0.11,
                "capacity_score": 0.7,
                "robustness_score": 0.82,
                "confidence": 0.87,
                "evidence_refs": ["research://alpha-2"],
            },
        ],
        "validation_gates": [
            {
                "gate_id": "walk-forward",
                "name": "Walk-forward validation",
                "passed": True,
                "score": 0.92,
                "minimum_score": 0.8,
                "evidence_refs": ["validation://wf"],
            },
            {
                "gate_id": "stress",
                "name": "Regime stress test",
                "passed": True,
                "score": 0.9,
                "minimum_score": 0.8,
                "evidence_refs": ["validation://stress"],
            },
        ],
        "selected_candidate_id": "alpha-1",
        "minimum_candidate_confidence": 0.9,
        "minimum_robustness_score": 0.85,
        "minimum_validation_pass_rate": 1,
        "maximum_allowed_drawdown": 0.1,
        "required_healthy_cycles": 2,
        "research_evidence_refs": ["portfolio://311", "research://factory"],
        "risk_decision": "allow",
    }
    data.update(overrides)
    return StrategyFactoryCreate(**data)


def act(service, record, action, **kwargs):
    return service.act(
        record.record_id,
        record.workspace_id,
        StrategyFactoryActionRequest(action=action, actor="human-reviewer", **kwargs),
    )


def test_complete_strategy_lifecycle():
    service = StrategyFactoryService()
    record = service.create(payload())

    assert record.state == StrategyFactoryState.DRAFT
    assert record.validation_pass_rate == 1

    act(service, record, "prepare-evidence")
    act(service, record, "research")
    act(service, record, "prepare-validation")
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="approval-1")
    act(service, record, "incubate", receipt_id="receipt-1", evidence_refs=["incubation://start"])
    act(
        service,
        record,
        "record-cycle",
        cycle_healthy=True,
        observed_alpha=0.1,
        observed_sharpe=1.7,
        observed_drawdown=0.07,
        observed_robustness=0.9,
        evidence_refs=["cycle://1"],
    )
    act(
        service,
        record,
        "record-cycle",
        cycle_healthy=True,
        observed_alpha=0.11,
        observed_sharpe=1.9,
        observed_drawdown=0.06,
        observed_robustness=0.92,
        evidence_refs=["cycle://2"],
    )
    promoted = act(service, record, "promote")

    assert promoted.state == StrategyFactoryState.PROMOTED
    assert promoted.consecutive_healthy_cycles == 2
    assert service.audit("ws-a")[-1].action == "promote"


def test_research_escalates_weak_candidate():
    service = StrategyFactoryService()
    weak = payload(
        candidates=[
            {
                "candidate_id": "weak",
                "name": "Weak alpha",
                "owner": "strategy-brain",
                "market": "EURUSD",
                "timeframe": "M5",
                "hypothesis": "Unproven hypothesis",
                "expected_alpha": 0.01,
                "expected_sharpe": 0.2,
                "maximum_drawdown": 0.2,
                "capacity_score": 0.5,
                "robustness_score": 0.5,
                "confidence": 0.5,
                "evidence_refs": ["research://weak"],
            }
        ],
        selected_candidate_id="weak",
    )
    record = service.create(weak)
    act(service, record, "prepare-evidence")
    researched = act(service, record, "research")
    assert researched.state == StrategyFactoryState.ESCALATED


def test_unhealthy_cycle_escalates_and_resets_counter():
    service = StrategyFactoryService()
    record = service.create(payload())
    act(service, record, "prepare-evidence")
    act(service, record, "research")
    act(service, record, "prepare-validation")
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="approval-2")
    act(service, record, "incubate", receipt_id="receipt-2", evidence_refs=["incubation://start"])
    escalated = act(
        service,
        record,
        "record-cycle",
        cycle_healthy=True,
        observed_drawdown=0.18,
        observed_robustness=0.9,
    )
    assert escalated.state == StrategyFactoryState.ESCALATED
    assert escalated.consecutive_healthy_cycles == 0


def test_risk_brain_block_is_authoritative():
    service = StrategyFactoryService()
    record = service.create(payload(risk_decision=RiskDecision.BLOCK, risk_reason="capital freeze"))
    blocked = act(service, record, "prepare-evidence")
    assert blocked.state == StrategyFactoryState.BLOCKED


def test_replay_protection():
    service = StrategyFactoryService()
    first = service.create(payload())
    act(service, first, "prepare-evidence")
    act(service, first, "research")
    act(service, first, "prepare-validation")
    act(service, first, "request-review")
    act(service, first, "approve", approval_token="shared-token")

    second = service.create(payload(source_key="factory-002"))
    act(service, second, "prepare-evidence")
    act(service, second, "research")
    act(service, second, "prepare-validation")
    act(service, second, "request-review")
    with pytest.raises(StrategyFactoryError, match="already used"):
        act(service, second, "approve", approval_token="shared-token")


def test_workspace_isolation_and_duplicate_source_key():
    service = StrategyFactoryService()
    record = service.create(payload())
    with pytest.raises(StrategyFactoryError, match="not found"):
        service.get(record.record_id, "ws-b")
    with pytest.raises(StrategyFactoryError, match="duplicate source key"):
        service.create(payload())


def test_selected_candidate_must_exist():
    with pytest.raises(ValidationError, match="selected_candidate_id"):
        payload(selected_candidate_id="missing")


def test_promotion_requires_healthy_cycles():
    service = StrategyFactoryService()
    record = service.create(payload())
    act(service, record, "prepare-evidence")
    act(service, record, "research")
    act(service, record, "prepare-validation")
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="approval-3")
    act(service, record, "incubate", receipt_id="receipt-3", evidence_refs=["incubation://start"])
    act(
        service,
        record,
        "record-cycle",
        cycle_healthy=True,
        observed_drawdown=0.05,
        observed_robustness=0.95,
    )
    with pytest.raises(StrategyFactoryError, match="insufficient healthy"):
        act(service, record, "promote")
