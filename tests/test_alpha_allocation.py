import pytest

from backend.app.phoenix.v21_55_alpha_allocation.models import (
    AlphaAllocation,
    DeploymentActionRequest,
    DeploymentCreate,
    DeploymentState,
    RiskDecision,
)
from backend.app.phoenix.v21_55_alpha_allocation.service import (
    CapitalDeploymentError,
    CapitalDeploymentService,
)


def payload(workspace="ws-1", source="source-1", risk=RiskDecision.ALLOW):
    return DeploymentCreate(
        workspace_id=workspace,
        source_key=source,
        strategy_factory_record_id="strategy-record-1",
        deployment_name="Core Alpha Deployment",
        total_capital=100000,
        allocations=[
            AlphaAllocation(
                allocation_id="alloc-1",
                strategy_id="strategy-1",
                capital_amount=40000,
                portfolio_weight=0.40,
                expected_alpha=0.14,
                expected_volatility=0.10,
                maximum_drawdown=0.08,
                capacity_limit=75000,
                liquidity_score=0.90,
                confidence=0.92,
                leverage=1.2,
                evidence_refs=["validation-1"],
            ),
            AlphaAllocation(
                allocation_id="alloc-2",
                strategy_id="strategy-2",
                capital_amount=30000,
                portfolio_weight=0.30,
                expected_alpha=0.10,
                expected_volatility=0.08,
                maximum_drawdown=0.06,
                capacity_limit=60000,
                liquidity_score=0.88,
                confidence=0.90,
                leverage=1.0,
                evidence_refs=["validation-2"],
            ),
        ],
        deployment_evidence_refs=["portfolio-verified", "strategy-promoted"],
        risk_decision=risk,
    )


def act(service, record, action, **kwargs):
    return service.act(
        record.record_id,
        record.workspace_id,
        DeploymentActionRequest(action=action, actor="tester", **kwargs),
    )


def test_full_lifecycle_to_verified():
    service = CapitalDeploymentService()
    record = service.create(payload())
    assert act(service, record, "prepare-evidence").state == DeploymentState.EVIDENCE_READY
    assert act(service, record, "analyze").state == DeploymentState.ANALYZED
    assert act(service, record, "prepare-deployment").state == DeploymentState.DEPLOYMENT_READY
    assert act(service, record, "request-review").state == DeploymentState.REVIEW_REQUIRED
    assert act(service, record, "approve", approval_token="approval-1").state == DeploymentState.APPROVED
    assert act(service, record, "deploy", receipt_id="receipt-1", evidence_refs=["deployment-proof"]).state == DeploymentState.DEPLOYING
    for index in range(record.required_healthy_cycles):
        state = act(
            service,
            record,
            "record-cycle",
            cycle_healthy=True,
            observed_drawdown=0.04,
            observed_total_leverage=1.1,
            observed_liquidity_score=0.85,
            evidence_refs=[f"cycle-{index}"],
        ).state
        assert state == DeploymentState.MONITORING
    assert act(service, record, "verify").state == DeploymentState.VERIFIED
    assert len(service.audit("ws-1")) >= 10


def test_constraint_breach_escalates():
    service = CapitalDeploymentService()
    data = payload()
    data.allocations[0].portfolio_weight = 0.60
    record = service.create(data)
    act(service, record, "prepare-evidence")
    assert act(service, record, "analyze").state == DeploymentState.ESCALATED


def test_unhealthy_monitoring_cycle_escalates():
    service = CapitalDeploymentService()
    record = service.create(payload())
    for action in ("prepare-evidence", "analyze", "prepare-deployment", "request-review"):
        act(service, record, action)
    act(service, record, "approve", approval_token="approval-2")
    act(service, record, "deploy", receipt_id="receipt-2")
    result = act(service, record, "record-cycle", cycle_healthy=True, observed_drawdown=0.30)
    assert result.state == DeploymentState.ESCALATED
    assert result.consecutive_healthy_cycles == 0


def test_risk_brain_block_is_authoritative():
    service = CapitalDeploymentService()
    record = service.create(payload(risk=RiskDecision.BLOCK))
    assert act(service, record, "prepare-evidence").state == DeploymentState.BLOCKED


def test_replay_protection():
    service = CapitalDeploymentService()
    first = service.create(payload(source="source-a"))
    second = service.create(payload(source="source-b"))
    for record in (first, second):
        for action in ("prepare-evidence", "analyze", "prepare-deployment", "request-review"):
            act(service, record, action)
    act(service, first, "approve", approval_token="shared-token")
    with pytest.raises(CapitalDeploymentError, match="replay"):
        act(service, second, "approve", approval_token="shared-token")


def test_duplicate_source_and_workspace_isolation():
    service = CapitalDeploymentService()
    record = service.create(payload())
    with pytest.raises(CapitalDeploymentError, match="duplicate"):
        service.create(payload())
    with pytest.raises(CapitalDeploymentError, match="not found"):
        service.get(record.record_id, "other-workspace")


def test_validation_rejects_overallocation():
    with pytest.raises(ValueError, match="allocated capital"):
        DeploymentCreate(
            workspace_id="ws",
            source_key="source",
            strategy_factory_record_id="record",
            deployment_name="invalid",
            total_capital=100,
            allocations=[
                AlphaAllocation(
                    allocation_id="a",
                    strategy_id="s",
                    capital_amount=101,
                    portfolio_weight=0.5,
                    expected_alpha=0.1,
                    expected_volatility=0.1,
                    maximum_drawdown=0.1,
                    capacity_limit=200,
                    liquidity_score=0.9,
                    confidence=0.9,
                    evidence_refs=["e"],
                )
            ],
            deployment_evidence_refs=["e"],
        )
