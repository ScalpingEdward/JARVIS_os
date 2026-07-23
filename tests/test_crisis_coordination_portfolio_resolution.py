import pytest
from pydantic import ValidationError

from backend.app.phoenix.v21_61_crisis_coordination_portfolio_resolution.models import (
    CrisisAction, CrisisCreate, CrisisPolicy, CrisisPortfolio, CrisisState, ResolutionDirective,
)
from backend.app.phoenix.v21_61_crisis_coordination_portfolio_resolution.service import (
    CrisisGovernanceService, GovernanceError,
)


def portfolio(**overrides):
    data = {
        "portfolio_id": "portfolio-a", "capital": 1_000_000, "drawdown_pct": 4,
        "liquidity_score": 80, "leverage": 1.2, "stress_score": 25,
        "projected_loss_pct": 3, "operational_health": 90, "recovery_capacity": 85,
    }
    data.update(overrides)
    return CrisisPortfolio(**data)


def payload(**overrides):
    data = {
        "workspace_id": "workspace-a", "source_key": "incident-source-1", "incident_id": "incident-1",
        "portfolios": [portfolio()],
        "directives": [ResolutionDirective(portfolio_id="portfolio-a", action="increase-liquidity", magnitude_pct=15, rationale="protect liquidity")],
        "evidence_refs": ["systemic-risk:record-1"],
        "policy": CrisisPolicy(stabilization_cycles_required=2, resolution_cycles_required=2),
    }
    data.update(overrides)
    return CrisisCreate(**data)


def advance(service, record_id):
    actions = [
        ("prepare-evidence", {}), ("assess", {}), ("prepare-coordination", {}),
        ("request-review", {}), ("approve", {"approval_token": "approval-1"}),
        ("activate-coordination", {"operation_receipt": "coordination-1"}),
        ("confirm-containment", {}),
    ]
    for action, extra in actions:
        service.act(record_id, "workspace-a", CrisisAction(action=action, actor="operator", **extra))


def test_full_crisis_resolution_lifecycle():
    service = CrisisGovernanceService()
    record = service.create(payload())
    advance(service, record.record_id)
    for _ in range(2):
        service.act(record.record_id, "workspace-a", CrisisAction(action="observe", actor="monitor", portfolios=[portfolio()]))
    assert record.state == CrisisState.STABILIZED
    service.act(record.record_id, "workspace-a", CrisisAction(action="prepare-resolution", actor="operator"))
    service.act(record.record_id, "workspace-a", CrisisAction(action="execute-resolution", actor="operator", operation_receipt="resolution-1"))
    service.act(record.record_id, "workspace-a", CrisisAction(action="begin-recovery-monitoring", actor="operator"))
    for _ in range(2):
        service.act(record.record_id, "workspace-a", CrisisAction(action="observe", actor="monitor", portfolios=[portfolio()]))
    service.act(record.record_id, "workspace-a", CrisisAction(action="confirm-resolved", actor="operator", operation_receipt="resolved-1"))
    assert record.state == CrisisState.RESOLVED
    assert service.audit


def test_emergency_observation_escalates():
    service = CrisisGovernanceService()
    record = service.create(payload())
    advance(service, record.record_id)
    distressed = portfolio(drawdown_pct=25, liquidity_score=20, stress_score=95, projected_loss_pct=22, operational_health=30, recovery_capacity=20)
    service.act(record.record_id, "workspace-a", CrisisAction(action="observe", actor="monitor", portfolios=[distressed]))
    assert record.state == CrisisState.ESCALATED
    assert "projected_loss_exceeded" in record.violations


def test_replay_and_risk_brain_blocks():
    service = CrisisGovernanceService()
    first = service.create(payload())
    advance(service, first.record_id)
    second = service.create(payload(source_key="incident-source-2", incident_id="incident-2"))
    for action in ["prepare-evidence", "assess", "prepare-coordination", "request-review"]:
        service.act(second.record_id, "workspace-a", CrisisAction(action=action, actor="operator"))
    with pytest.raises(GovernanceError, match="replay"):
        service.act(second.record_id, "workspace-a", CrisisAction(action="approve", actor="operator", approval_token="approval-1"))
    blocked = service.create(payload(source_key="incident-source-3", incident_id="incident-3", risk_brain_blocked=True))
    with pytest.raises(GovernanceError, match="Risk Brain"):
        service.act(blocked.record_id, "workspace-a", CrisisAction(action="prepare-evidence", actor="operator"))


def test_duplicate_workspace_isolation_and_validation():
    service = CrisisGovernanceService()
    record = service.create(payload())
    with pytest.raises(GovernanceError, match="duplicate"):
        service.create(payload())
    with pytest.raises(KeyError):
        service.get(record.record_id, "workspace-b")
    with pytest.raises(ValidationError):
        CrisisCreate(
            workspace_id="w", source_key="s", incident_id="i", portfolios=[portfolio()],
            directives=[ResolutionDirective(portfolio_id="unknown", action="isolate-portfolio", rationale="invalid")],
        )
