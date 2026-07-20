from uuid import uuid4

import pytest

from app.executive_broker_connectivity.models import BrokerConnectivityState, BrokerSessionAssessmentCreate, BrokerSessionObservation, ReconnectRequest
from app.executive_broker_connectivity.service import executive_broker_connectivity_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    executive_broker_connectivity_service.reset()


def valid_payload(**changes) -> BrokerSessionAssessmentCreate:
    payload = BrokerSessionAssessmentCreate(
        workspace_id="workspace-a",
        source_key=f"broker-session-{uuid4()}",
        actor_id="operator-1",
        broker_id="paper-primary",
        broker_kind="paper",
        environment="paper",
        endpoint="https://paper-broker.local",
        account_reference="account-ref-1",
    )
    return payload.model_copy(update=changes)


def test_session_ready() -> None:
    record = executive_broker_connectivity_service.assess(valid_payload())
    assert record.state == BrokerConnectivityState.session_ready
    assert record.session_ready is True
    assert record.autonomous_actions_enabled is False


def test_authentication_required() -> None:
    observation = BrokerSessionObservation(authentication_valid=False)
    record = executive_broker_connectivity_service.assess(valid_payload(observation=observation))
    assert record.state == BrokerConnectivityState.authentication_required


def test_maintenance_mode() -> None:
    observation = BrokerSessionObservation(maintenance_mode=True)
    record = executive_broker_connectivity_service.assess(valid_payload(observation=observation))
    assert record.state == BrokerConnectivityState.maintenance_mode


def test_rate_limited() -> None:
    observation = BrokerSessionObservation(rate_limited=True)
    record = executive_broker_connectivity_service.assess(valid_payload(observation=observation))
    assert record.state == BrokerConnectivityState.rate_limited


def test_connection_degraded_and_reconnect() -> None:
    observation = BrokerSessionObservation(connection_healthy=False, reconnect_required=True, reconnect_acknowledged=False)
    record = executive_broker_connectivity_service.assess(valid_payload(observation=observation))
    assert record.state == BrokerConnectivityState.connection_degraded
    recovered = executive_broker_connectivity_service.reconnect(ReconnectRequest(workspace_id=record.workspace_id, session_id=record.session_id, actor_id="operator-2"))
    assert recovered.state == BrokerConnectivityState.session_ready


def test_raw_credentials_blocked() -> None:
    observation = BrokerSessionObservation(raw_credentials_present=True)
    record = executive_broker_connectivity_service.assess(valid_payload(observation=observation))
    assert record.state == BrokerConnectivityState.blocked


def test_risk_brain_blocked() -> None:
    record = executive_broker_connectivity_service.assess(valid_payload(risk_brain_clear=False))
    assert record.state == BrokerConnectivityState.blocked


def test_duplicate_session_rejected() -> None:
    first = valid_payload()
    executive_broker_connectivity_service.assess(first)
    second = valid_payload(session_id=first.session_id)
    with pytest.raises(ValueError, match="Duplicate broker session ID"):
        executive_broker_connectivity_service.assess(second)


def test_workspace_isolation() -> None:
    record = executive_broker_connectivity_service.assess(valid_payload())
    assert executive_broker_connectivity_service.get(record.id, "workspace-b") is None
    assert executive_broker_connectivity_service.list_sessions("workspace-b") == []
