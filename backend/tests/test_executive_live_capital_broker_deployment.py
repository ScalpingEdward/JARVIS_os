import pytest
from pydantic import ValidationError

from app.executive_live_capital_broker_deployment.models import (
    AccountType,
    BrokerCandidate,
    BrokerDeploymentPolicy,
    DeploymentState,
    LiveCapitalDeploymentCreate,
)
from app.executive_live_capital_broker_deployment.service import ExecutiveLiveCapitalBrokerDeploymentService


def candidate(**overrides):
    data = dict(
        broker_id="broker-a",
        account_id="live-1",
        account_type=AccountType.live,
        base_currency="EUR",
        regulated=True,
        withdrawals_verified=True,
        operational_health=90,
        requested_funding=4000,
    )
    data.update(overrides)
    return BrokerCandidate(**data)


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="deployment-1",
        actor_id="master-brano",
        treasury_approved_live_capital=10000,
        human_approved=True,
        risk_brain_clear=True,
        candidates=[candidate(), candidate(broker_id="broker-b", account_id="live-2", requested_funding=6000)],
        policy=BrokerDeploymentPolicy(
            max_broker_share=0.6,
            max_account_share=0.6,
            max_new_accounts_per_cycle=2,
        ),
    )
    data.update(overrides)
    return LiveCapitalDeploymentCreate(**data)


def test_full_live_deployment():
    service = ExecutiveLiveCapitalBrokerDeploymentService()
    result = service.create(payload())
    assert result.state == DeploymentState.fund_full
    assert result.approved_deployment_capital == 10000
    assert all(line.deployable for line in result.funding_lines)


def test_human_approval_holds_funding():
    service = ExecutiveLiveCapitalBrokerDeploymentService()
    result = service.create(payload(human_approved=False))
    assert result.state == DeploymentState.hold
    assert result.approved_deployment_capital == 0
    assert result.unallocated_capital == 10000


def test_risk_brain_blocks_deployment():
    service = ExecutiveLiveCapitalBrokerDeploymentService()
    result = service.create(payload(risk_brain_clear=False))
    assert result.state == DeploymentState.blocked
    assert result.approved_deployment_capital == 0


def test_prop_account_is_rejected():
    with pytest.raises(ValidationError):
        payload(candidates=[candidate(account_type=AccountType.prop)])


def test_unverified_broker_is_held():
    service = ExecutiveLiveCapitalBrokerDeploymentService()
    result = service.create(payload(candidates=[candidate(withdrawals_verified=False)]))
    assert result.state == DeploymentState.blocked


def test_workspace_isolation_and_duplicate_protection():
    service = ExecutiveLiveCapitalBrokerDeploymentService()
    created = service.create(payload())
    assert service.get(created.id, "other") is None
    with pytest.raises(ValueError):
        service.create(payload())
