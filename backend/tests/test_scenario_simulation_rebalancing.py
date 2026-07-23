import pytest

from app.schemas.scenario_simulation_rebalancing import (
    ScenarioAction,
    ScenarioRecordCreate,
    ScenarioState,
)
from app.services.scenario_simulation_rebalancing import ScenarioSimulationService


@pytest.fixture
def service() -> ScenarioSimulationService:
    return ScenarioSimulationService()


def payload(workspace: str = "ws-a", source_key: str = "scenario-1") -> ScenarioRecordCreate:
    return ScenarioRecordCreate(
        workspace_id=workspace,
        source_key=source_key,
        portfolio_value=1_000_000,
        max_acceptable_loss_pct=0.08,
        max_turnover_pct=0.25,
        requested_by="portfolio-analyst",
        sleeves=[
            {
                "name": "equities",
                "current_weight": 0.6,
                "target_weight": 0.55,
                "expected_return_pct": 0.09,
                "volatility_pct": 0.18,
                "liquidity_score": 85,
                "factor_sensitivities": {"growth": 0.9, "rates": -0.3},
            },
            {
                "name": "rates",
                "current_weight": 0.4,
                "target_weight": 0.45,
                "expected_return_pct": 0.04,
                "volatility_pct": 0.08,
                "liquidity_score": 92,
                "factor_sensitivities": {"growth": -0.2, "rates": 0.7},
            },
        ],
        shocks=[
            {
                "factor": "growth",
                "shock_pct": -0.2,
                "probability": 0.3,
                "liquidity_multiplier": 1.4,
                "volatility_multiplier": 1.5,
                "correlation_shift": 0.25,
                "confidence": 0.9,
                "freshness": 0.95,
                "provenance": ["macro-scenario", "risk-brain"],
            }
        ],
    )


def test_scores_scenario_and_returns_normalized_recommendation(service: ScenarioSimulationService) -> None:
    record = service.create(payload())
    assert record.state in {ScenarioState.SCORED, ScenarioState.REVIEW_REQUIRED}
    assert 0 <= record.scores.portfolio_resilience <= 100
    assert sum(record.recommended_weights.values()) == pytest.approx(1, abs=1e-5)


def test_duplicate_source_key_is_rejected_per_workspace(service: ScenarioSimulationService) -> None:
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.create(payload("ws-b")).workspace_id == "ws-b"


def test_workspace_isolation(service: ScenarioSimulationService) -> None:
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get(record.record_id, "ws-b")


def test_human_approval_and_replay_protection(service: ScenarioSimulationService) -> None:
    record = service.create(payload())
    action = ScenarioAction(action="approve", actor="risk-officer", operation_id="op-1")
    approved = service.act(record.record_id, "ws-a", action)
    version = approved.version
    replayed = service.act(record.record_id, "ws-a", action)
    assert approved.state == ScenarioState.APPROVED
    assert approved.approved_by == "risk-officer"
    assert replayed.version == version


def test_risk_brain_hard_block_is_authoritative(service: ScenarioSimulationService) -> None:
    record = service.create(payload())
    blocked = service.act(
        record.record_id,
        "ws-a",
        ScenarioAction(action="activate", actor="operator", operation_id="op-block"),
        risk_blocked=True,
    )
    assert blocked.state == ScenarioState.BLOCKED
    assert "risk-brain-hard-block" in blocked.risk_flags


def test_module_never_mutates_allocations_or_executes(service: ScenarioSimulationService) -> None:
    status = service.status()
    assert status["allocation_mutation_enabled"] is False
    assert status["execution_enabled"] is False
