from app.executive_capital_allocation_deployment.models import AllocationCandidate, AllocationInput, AllocationState
from app.executive_capital_allocation_deployment.service import ExecutiveCapitalAllocationDeploymentService


def payload(**overrides):
    data = dict(
        workspace_id="ws-a",
        actor_id="risk-officer",
        source_key="alloc-1",
        approved_total_capital=100000,
        reserve_capital_pct=20,
        human_approval=True,
        candidates=[
            AllocationCandidate(strategy_id="ict", account_id="a1", symbol="XAUUSD", requested_capital=30000, requested_risk_pct=1, confidence_score=90, stability_score=88, correlation_score=25, current_account_exposure_pct=5, current_symbol_exposure_pct=5),
            AllocationCandidate(strategy_id="breakout", account_id="a2", symbol="EURUSD", requested_capital=25000, requested_risk_pct=0.75, confidence_score=82, stability_score=85, correlation_score=30, current_account_exposure_pct=5, current_symbol_exposure_pct=5),
        ],
    )
    data.update(overrides)
    return AllocationInput(**data)


def test_full_or_rebalance_allocation_is_governed():
    service = ExecutiveCapitalAllocationDeploymentService()
    result = service.assess(payload())
    assert result.state in {AllocationState.deploy_full, AllocationState.rebalance}
    assert result.allocated_capital > 0
    assert result.reserve_capital == 20000
    assert result.autonomous_deployment_enabled is False


def test_missing_human_approval_holds_deployment():
    service = ExecutiveCapitalAllocationDeploymentService()
    result = service.assess(payload(human_approval=False))
    assert result.state == AllocationState.hold
    assert result.allocated_capital == 0


def test_blocked_risk_brain_blocks_allocation():
    service = ExecutiveCapitalAllocationDeploymentService()
    result = service.assess(payload(risk_brain_state="blocked"))
    assert result.state == AllocationState.blocked
    assert all(line.approved_capital == 0 for line in result.deployment_plan)


def test_high_correlation_reduces_deployment():
    service = ExecutiveCapitalAllocationDeploymentService()
    candidate = AllocationCandidate(strategy_id="grid", account_id="a1", symbol="XAUUSD", requested_capital=30000, requested_risk_pct=1, confidence_score=85, stability_score=80, correlation_score=90, current_account_exposure_pct=5, current_symbol_exposure_pct=5)
    result = service.assess(payload(candidates=[candidate]))
    assert result.state == AllocationState.deploy_reduced
    assert result.deployment_plan[0].approved_risk_pct == 0.5


def test_duplicate_source_key_and_workspace_isolation():
    service = ExecutiveCapitalAllocationDeploymentService()
    first = service.assess(payload())
    assert service.get(first.id, "ws-b") is None
    try:
        service.assess(payload())
        assert False, "duplicate source key should fail"
    except ValueError:
        pass
