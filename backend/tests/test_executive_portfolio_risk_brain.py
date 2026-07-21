import pytest

from app.executive_portfolio_risk_brain.models import (
    PortfolioRiskAssessmentCreate,
    PortfolioRiskExecuteRequest,
    PortfolioRiskState,
)
from app.executive_portfolio_risk_brain.service import PortfolioRiskBrainService


def payload(**overrides):
    values = {
        "workspace_id": "ws-a",
        "source_key": "risk-1",
        "actor_id": "tester",
        "account_state_healthy": True,
        "equity": 100000,
        "balance": 100000,
        "free_margin": 95000,
        "margin_level": 800,
        "current_drawdown_pct": 1,
        "daily_drawdown_pct": 0.5,
        "portfolio_heat_pct": 20,
        "risk_budget_used": 1000,
        "risk_budget_limit": 5000,
        "proposed_risk_amount": 500,
        "gross_exposure": 10000,
        "account_risk_approved": True,
        "prop_rules_approved": True,
        "human_approved": True,
    }
    values.update(overrides)
    return PortfolioRiskAssessmentCreate(**values)


def test_healthy_risk_approval_and_metrics():
    service = PortfolioRiskBrainService()
    record = service.create(payload())
    assert record.state == PortfolioRiskState.RISK_APPROVED
    assert record.remaining_risk_budget == 4000
    assert record.projected_portfolio_heat_pct == 30


def test_requires_v1903_account_state():
    service = PortfolioRiskBrainService()
    record = service.create(payload(account_state_healthy=False))
    assert record.state == PortfolioRiskState.ACCOUNT_STATE_REQUIRED


def test_upstream_risk_brain_fails_closed():
    service = PortfolioRiskBrainService()
    record = service.create(payload(risk_brain_blocked=True))
    assert record.state == PortfolioRiskState.BLOCKED


def test_risk_budget_and_concentration_guards():
    service = PortfolioRiskBrainService()
    budget = service.create(payload(source_key="budget", risk_budget_used=4800, proposed_risk_amount=500))
    concentration = service.create(payload(source_key="concentration", largest_symbol_exposure_pct=50))
    assert budget.state == PortfolioRiskState.RISK_BUDGET_EXHAUSTED
    assert concentration.state == PortfolioRiskState.CONCENTRATION_GUARD


def test_drawdown_halt_and_manual_reduce_only():
    service = PortfolioRiskBrainService()
    halt = service.create(payload(source_key="halt", current_drawdown_pct=9))
    halt = service.execute(halt.id, "ws-a", PortfolioRiskExecuteRequest(actor_id="ops", action="reassess"))
    assert halt.state == PortfolioRiskState.HALT_REQUIRED
    assert halt.trading_halted is True
    normal = service.create(payload(source_key="reduce"))
    normal = service.execute(normal.id, "ws-a", PortfolioRiskExecuteRequest(actor_id="ops", action="reduce-only"))
    assert normal.state == PortfolioRiskState.REDUCE_ONLY
    assert normal.reduce_only is True


def test_human_approval_and_activation():
    service = PortfolioRiskBrainService()
    record = service.create(payload(human_approved=False))
    assert record.state == PortfolioRiskState.APPROVAL_REQUIRED
    record = service.execute(
        record.id,
        "ws-a",
        PortfolioRiskExecuteRequest(actor_id="approver", action="activate", human_approved=True),
    )
    assert record.state == PortfolioRiskState.RISK_APPROVED


def test_duplicate_workspace_isolation_and_audit():
    service = PortfolioRiskBrainService()
    record = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    other = service.create(payload(workspace_id="ws-b"))
    assert service.get(record.id, "ws-b") is None
    assert service.get(other.id, "ws-b") is not None
    assert len(service.audit_records("ws-a")) == 1
