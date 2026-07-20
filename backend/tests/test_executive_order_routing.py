from uuid import uuid4

import pytest

from app.executive_order_routing.models import ApprovalRequest, OrderIntentCreate, OrderRoutingObservation, OrderRoutingState
from app.executive_order_routing.service import executive_order_routing_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    executive_order_routing_service.reset()


def payload(**changes):
    data = dict(
        workspace_id="ws-1",
        source_key="source-1",
        actor_id="operator-1",
        broker_session_id=uuid4(),
        market_data_subscription_id=uuid4(),
        account_reference="acct-1",
        canonical_symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume=0.1,
        stop_loss=2300.0,
        take_profit=2350.0,
        strategy_id="smc-scalper",
    )
    data.update(changes)
    return OrderIntentCreate(**data)


def test_human_approval_gate_and_dispatch() -> None:
    record = executive_order_routing_service.assess(payload())
    assert record.state == OrderRoutingState.approval_required
    approved = executive_order_routing_service.approve(ApprovalRequest(workspace_id="ws-1", intent_id=record.intent_id, actor_id="human-1"))
    assert approved.state == OrderRoutingState.ready_for_dispatch
    assert approved.dispatch_allowed is True


def test_risk_brain_block_is_absolute() -> None:
    record = executive_order_routing_service.assess(payload(risk_brain_clear=False))
    assert record.state == OrderRoutingState.blocked
    assert record.dispatch_allowed is False


def test_market_data_dependency() -> None:
    observation = OrderRoutingObservation(market_data_state="gap-detected")
    record = executive_order_routing_service.assess(payload(observation=observation))
    assert record.state == OrderRoutingState.market_data_required


def test_broker_session_dependency() -> None:
    observation = OrderRoutingObservation(broker_session_state="connection-degraded")
    record = executive_order_routing_service.assess(payload(observation=observation))
    assert record.state == OrderRoutingState.broker_session_required


def test_exposure_limit_rejects_order() -> None:
    observation = OrderRoutingObservation(exposure_within_limits=False)
    record = executive_order_routing_service.assess(payload(observation=observation))
    assert record.state == OrderRoutingState.risk_rejected


def test_invalid_stop_loss_rejects_order() -> None:
    observation = OrderRoutingObservation(stop_loss_valid=False)
    record = executive_order_routing_service.assess(payload(observation=observation))
    assert record.state == OrderRoutingState.invalid_order


def test_duplicate_intent_is_rejected() -> None:
    intent_id = uuid4()
    executive_order_routing_service.assess(payload(intent_id=intent_id))
    with pytest.raises(ValueError, match="Duplicate order intent ID"):
        executive_order_routing_service.assess(payload(source_key="source-2", intent_id=intent_id))


def test_workspace_isolation() -> None:
    record = executive_order_routing_service.assess(payload())
    assert executive_order_routing_service.get(record.id, "other-workspace") is None


def test_approval_denial_keeps_order_blocked() -> None:
    record = executive_order_routing_service.assess(payload())
    denied = executive_order_routing_service.approve(ApprovalRequest(workspace_id="ws-1", intent_id=record.intent_id, actor_id="human-1", approved=False))
    assert denied.state == OrderRoutingState.blocked
    assert denied.dispatch_allowed is False
