from app.connectors.models import ConnectorAction, ConnectorCreate, ConnectorHealthUpdate, ConnectorKind, ConnectorPermission, ConnectorState
from app.connectors.service import connector_service


def setup_function() -> None:
    connector_service.reset()


def test_connector_lifecycle_and_health() -> None:
    connector = connector_service.create(
        ConnectorCreate(
            name="GitHub",
            kind=ConnectorKind.github,
            permissions={ConnectorPermission.read, ConnectorPermission.write},
            secret_refs=["vault://github/token"],
            rate_limit_per_minute=120,
        )
    )
    assert connector.state == ConnectorState.disabled
    assert "vault://github/token" in connector.secret_refs

    enabled = connector_service.transition(connector.id, ConnectorAction(action="enable"))
    assert enabled is not None
    assert enabled.state == ConnectorState.connecting

    healthy = connector_service.update_health(connector.id, ConnectorHealthUpdate(healthy=True, latency_ms=42))
    assert healthy is not None
    assert healthy.state == ConnectorState.healthy

    paused = connector_service.transition(connector.id, ConnectorAction(action="pause", reason="maintenance"))
    assert paused is not None
    assert paused.state == ConnectorState.paused
    assert len(connector_service.audit(connector.id)) == 4


def test_failed_health_enters_reconnect_when_enabled() -> None:
    connector = connector_service.create(ConnectorCreate(name="MT5", kind=ConnectorKind.mt5, auto_reconnect=True))
    connector_service.transition(connector.id, ConnectorAction(action="enable"))
    updated = connector_service.update_health(connector.id, ConnectorHealthUpdate(healthy=False, error="timeout"))
    assert updated is not None
    assert updated.state == ConnectorState.connecting
    assert updated.last_error == "timeout"


def test_platform_is_advisory_and_no_auto_merge() -> None:
    status = connector_service.status()
    assert status.automatic_order_execution is False
    assert status.automatic_merge is False
