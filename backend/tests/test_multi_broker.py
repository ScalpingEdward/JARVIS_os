import pytest

from app.multi_broker.models import (
    AccountMode,
    BrokerAccountCreate,
    BrokerConnectionCreate,
    BrokerRuleProfile,
    ConnectorState,
    SymbolMapping,
)
from app.multi_broker.service import multi_broker_service


def setup_function() -> None:
    multi_broker_service.reset()


def test_connector_must_remain_read_only() -> None:
    with pytest.raises(ValueError, match="read-only"):
        multi_broker_service.register_broker(BrokerConnectionCreate(name="Unsafe Broker", read_only=False))


def test_symbol_mapping_and_heartbeat() -> None:
    broker = multi_broker_service.register_broker(
        BrokerConnectionCreate(
            name="FTMO MT5",
            state=ConnectorState.offline,
            symbol_mappings=[SymbolMapping(canonical_symbol="XAUUSD", broker_symbol="XAUUSD.a")],
        )
    )
    updated = multi_broker_service.heartbeat(broker.id, ConnectorState.online, 42)
    assert updated is not None
    assert updated.state == ConnectorState.online
    assert updated.latency_ms == 42
    resolution = multi_broker_service.resolve_symbol(broker.id, "XAUUSD")
    assert resolution is not None
    assert resolution.broker_symbol == "XAUUSD.a"


def test_fleet_blocks_account_at_rule_limit() -> None:
    broker = multi_broker_service.register_broker(
        BrokerConnectionCreate(
            name="Funded Account Provider",
            state=ConnectorState.online,
            rule_profile=BrokerRuleProfile(daily_drawdown_pct=4.0, max_drawdown_pct=8.0),
        )
    )
    multi_broker_service.add_account(
        BrokerAccountCreate(
            broker_id=broker.id,
            external_account_id="ACC-100K",
            label="100K Funded",
            mode=AccountMode.funded,
            balance=100000,
            equity=96500,
            daily_drawdown_pct=4.1,
            total_drawdown_pct=3.5,
        )
    )
    report = multi_broker_service.fleet_status()
    assert report.owner_name == "MASTER Brano"
    assert report.blocked_accounts == 1
    assert report.automatic_order_execution is False
    assert report.requires_human_approval is True


def test_fleet_totals_multiple_brokers() -> None:
    first = multi_broker_service.register_broker(BrokerConnectionCreate(name="Broker One", state=ConnectorState.online))
    second = multi_broker_service.register_broker(BrokerConnectionCreate(name="Broker Two", state=ConnectorState.degraded))
    multi_broker_service.add_account(
        BrokerAccountCreate(
            broker_id=first.id,
            external_account_id="ONE-1",
            label="Live One",
            mode=AccountMode.live,
            balance=10000,
            equity=10100,
        )
    )
    multi_broker_service.add_account(
        BrokerAccountCreate(
            broker_id=second.id,
            external_account_id="TWO-1",
            label="Demo Two",
            mode=AccountMode.demo,
            balance=5000,
            equity=4900,
        )
    )
    report = multi_broker_service.fleet_status()
    assert report.brokers == 2
    assert report.accounts == 2
    assert report.total_balance == 15000
    assert report.total_equity == 15000
    assert report.degraded_brokers == 1
