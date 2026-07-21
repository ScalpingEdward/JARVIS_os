from app.executive_mt5_strategy_runtime_orchestrator.models import (
    StrategyCandidate,
    StrategyRuntimeAssessmentCreate,
    StrategyRuntimeExecuteRequest,
    StrategyRuntimeState,
)
from app.executive_mt5_strategy_runtime_orchestrator.service import StrategyRuntimeOrchestratorService


def candidate(**updates):
    base = dict(
        strategy_id="smc-xau-1",
        symbol="XAUUSD",
        side="buy",
        signal_age_seconds=10,
        confidence=0.82,
        expected_rr=3.0,
        requested_risk_amount=50,
        regime="london-trend",
        priority=10,
    )
    base.update(updates)
    return StrategyCandidate(**base)


def payload(**updates):
    base = dict(
        workspace_id="ws-a",
        source_key="source-1",
        actor_id="tester",
        portfolio_ready=True,
        candidates=[candidate()],
        current_regime="london-trend",
        max_signal_age_seconds=120,
        minimum_confidence=0.6,
        minimum_expected_rr=1.5,
        max_concurrent_strategies=3,
        active_strategy_count=0,
        available_risk_budget=500,
        account_risk_approved=True,
        prop_rules_approved=True,
        human_approved=True,
    )
    base.update(updates)
    return StrategyRuntimeAssessmentCreate(**base)


def test_requires_portfolio_ready():
    service = StrategyRuntimeOrchestratorService()
    assert service.create(payload(portfolio_ready=False)).state == StrategyRuntimeState.PORTFOLIO_REQUIRED


def test_rejects_stale_signal():
    service = StrategyRuntimeOrchestratorService()
    assert service.create(payload(candidates=[candidate(signal_age_seconds=999)])).state == StrategyRuntimeState.SIGNAL_STALE


def test_rejects_regime_mismatch():
    service = StrategyRuntimeOrchestratorService()
    assert service.create(payload(current_regime="range")).state == StrategyRuntimeState.REGIME_MISMATCH


def test_rejects_low_quality_strategy():
    service = StrategyRuntimeOrchestratorService()
    assert service.create(payload(candidates=[candidate(confidence=0.2)])).state == StrategyRuntimeState.STRATEGY_INVALID


def test_detects_direction_conflict():
    service = StrategyRuntimeOrchestratorService()
    candidates = [candidate(strategy_id="a"), candidate(strategy_id="b", side="sell")]
    assert service.create(payload(candidates=candidates)).state == StrategyRuntimeState.CONFLICT_DETECTED


def test_rejects_capacity():
    service = StrategyRuntimeOrchestratorService()
    assert service.create(payload(max_concurrent_strategies=1, active_strategy_count=1)).state == StrategyRuntimeState.CAPACITY_REJECTED


def test_rejects_risk_budget():
    service = StrategyRuntimeOrchestratorService()
    assert service.create(payload(available_risk_budget=10)).state == StrategyRuntimeState.RISK_REJECTED


def test_requires_human_approval():
    service = StrategyRuntimeOrchestratorService()
    assert service.create(payload(human_approved=False)).state == StrategyRuntimeState.APPROVAL_REQUIRED


def test_progresses_to_runtime_active():
    service = StrategyRuntimeOrchestratorService()
    record = service.create(payload())
    assert record.state == StrategyRuntimeState.SCHEDULED
    updated = service.execute(record.id, "ws-a", StrategyRuntimeExecuteRequest(actor_id="operator", dispatch_requested=True, dispatch_acknowledged=True, execution_started=True, runtime_reconciled=True))
    assert updated.state == StrategyRuntimeState.RUNTIME_ACTIVE


def test_pause_has_priority():
    service = StrategyRuntimeOrchestratorService()
    assert service.create(payload(pause_requested=True)).state == StrategyRuntimeState.PAUSED


def test_risk_brain_hard_block():
    service = StrategyRuntimeOrchestratorService()
    assert service.create(payload(risk_brain_blocked=True)).state == StrategyRuntimeState.BLOCKED


def test_duplicate_source_key_rejected():
    service = StrategyRuntimeOrchestratorService()
    service.create(payload())
    try:
        service.create(payload())
        assert False, "duplicate should fail"
    except ValueError:
        assert True


def test_workspace_isolation():
    service = StrategyRuntimeOrchestratorService()
    record = service.create(payload())
    assert service.get(record.id, "ws-b") is None
    assert service.list_records("ws-b") == []
