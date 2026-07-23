import pytest

from backend.app.phoenix.v21_60_cross_portfolio_contagion_systemic_risk.models import (
    ContagionLink,
    PortfolioNode,
    SystemicRiskAction,
    SystemicRiskCreate,
    SystemicRiskState,
)
from backend.app.phoenix.v21_60_cross_portfolio_contagion_systemic_risk.service import (
    GovernanceError,
    SystemicRiskGovernanceService,
)


def node(portfolio_id: str, stress: float = 30, liquidity: float = 80, drawdown: float = 2) -> PortfolioNode:
    return PortfolioNode(
        portfolio_id=portfolio_id,
        gross_exposure=1_000_000,
        net_exposure=250_000,
        drawdown_pct=drawdown,
        liquidity_score=liquidity,
        leverage=1.5,
        stress_score=stress,
        capital_share_pct=50,
    )


def link(probability: float = 0.2, correlation: float = 0.3) -> ContagionLink:
    return ContagionLink(
        source_portfolio_id="p1",
        target_portfolio_id="p2",
        correlation=correlation,
        shared_factor_exposure_pct=25,
        shared_liquidity_dependency_pct=20,
        transmission_probability=probability,
        loss_amplification=1.1,
    )


def payload(workspace: str = "w1", source: str = "source-1", blocked: bool = False) -> SystemicRiskCreate:
    return SystemicRiskCreate(
        workspace_id=workspace,
        source_key=source,
        portfolio_group_id="group-1",
        nodes=[node("p1"), node("p2")],
        links=[link()],
        evidence_refs=["rotation:317"],
        risk_brain_blocked=blocked,
    )


def action(name: str, **kwargs) -> SystemicRiskAction:
    return SystemicRiskAction(action=name, actor="test", **kwargs)


def advance_to_monitoring(service: SystemicRiskGovernanceService, record_id: str) -> None:
    for name in [
        "prepare-evidence", "map-network", "analyze", "prepare-containment", "request-review"
    ]:
        service.act(record_id, "w1", action(name))
    service.act(record_id, "w1", action("approve", approval_token="approval-1"))
    service.act(record_id, "w1", action("start-containment", operation_receipt="receipt-1"))


def test_full_stable_lifecycle() -> None:
    service = SystemicRiskGovernanceService()
    record = service.create(payload())
    advance_to_monitoring(service, record.record_id)
    for _ in range(3):
        record = service.act(record.record_id, "w1", action("observe"))
    assert record.state == SystemicRiskState.STABLE
    assert record.systemic_risk_score < record.policy.maximum_systemic_risk_score
    assert len(service.audit) == 11


def test_high_transmission_creates_systemic_alert() -> None:
    service = SystemicRiskGovernanceService()
    record = service.create(payload())
    advance_to_monitoring(service, record.record_id)
    stressed_nodes = [node("p1", stress=95, liquidity=30, drawdown=12), node("p2", stress=90, liquidity=25, drawdown=11)]
    risky_links = [link(probability=0.95, correlation=0.95)]
    record = service.act(
        record.record_id,
        "w1",
        action("observe", nodes=stressed_nodes, links=risky_links),
    )
    assert record.state == SystemicRiskState.SYSTEMIC_ALERT
    assert "projected_loss_exceeded" in record.violations


def test_replay_protection() -> None:
    service = SystemicRiskGovernanceService()
    first = service.create(payload())
    second = service.create(payload(source="source-2"))
    for record in [first, second]:
        for name in ["prepare-evidence", "map-network", "analyze", "prepare-containment", "request-review"]:
            service.act(record.record_id, "w1", action(name))
    service.act(first.record_id, "w1", action("approve", approval_token="shared"))
    with pytest.raises(GovernanceError, match="replay"):
        service.act(second.record_id, "w1", action("approve", approval_token="shared"))


def test_risk_brain_block_is_authoritative() -> None:
    service = SystemicRiskGovernanceService()
    record = service.create(payload(blocked=True))
    assert record.state == SystemicRiskState.BLOCKED
    with pytest.raises(GovernanceError, match="Risk Brain"):
        service.act(record.record_id, "w1", action("prepare-evidence"))
    revoked = service.act(record.record_id, "w1", action("revoke"))
    assert revoked.state == SystemicRiskState.REVOKED


def test_duplicate_and_workspace_isolation() -> None:
    service = SystemicRiskGovernanceService()
    record = service.create(payload())
    with pytest.raises(GovernanceError, match="duplicate"):
        service.create(payload())
    with pytest.raises(KeyError):
        service.get(record.record_id, "other-workspace")
    assert service.list("other-workspace") == []


def test_unknown_portfolio_link_rejected() -> None:
    service = SystemicRiskGovernanceService()
    bad = payload()
    bad.links[0].target_portfolio_id = "missing"
    with pytest.raises(GovernanceError, match="unknown portfolio"):
        service.create(bad)
