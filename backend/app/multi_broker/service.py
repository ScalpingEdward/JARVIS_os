from datetime import datetime, timezone
from uuid import UUID

from .models import (
    BrokerAccount,
    BrokerAccountCreate,
    BrokerConnection,
    BrokerConnectionCreate,
    BrokerFleetStatus,
    ConnectorState,
    SymbolResolution,
)


class MultiBrokerService:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._brokers: dict[UUID, BrokerConnection] = {}
        self._accounts: dict[UUID, BrokerAccount] = {}

    def register_broker(self, payload: BrokerConnectionCreate) -> BrokerConnection:
        if payload.read_only is not True:
            raise ValueError("Broker connectors must be read-only")
        broker = BrokerConnection(**payload.model_dump())
        self._brokers[broker.id] = broker
        return broker

    def list_brokers(self) -> list[BrokerConnection]:
        return list(self._brokers.values())

    def get_broker(self, broker_id: UUID) -> BrokerConnection | None:
        return self._brokers.get(broker_id)

    def heartbeat(self, broker_id: UUID, state: ConnectorState, latency_ms: int | None = None) -> BrokerConnection | None:
        broker = self._brokers.get(broker_id)
        if broker is None:
            return None
        updated = broker.model_copy(
            update={
                "state": state,
                "latency_ms": latency_ms,
                "last_heartbeat_at": datetime.now(timezone.utc),
            }
        )
        self._brokers[broker_id] = updated
        return updated

    def add_account(self, payload: BrokerAccountCreate) -> BrokerAccount:
        if payload.broker_id not in self._brokers:
            raise ValueError("Broker connection not found")
        account = BrokerAccount(**payload.model_dump())
        self._accounts[account.id] = account
        return account

    def list_accounts(self, broker_id: UUID | None = None) -> list[BrokerAccount]:
        accounts = list(self._accounts.values())
        if broker_id is not None:
            accounts = [item for item in accounts if item.broker_id == broker_id]
        return accounts

    def get_account(self, account_id: UUID) -> BrokerAccount | None:
        return self._accounts.get(account_id)

    def resolve_symbol(self, broker_id: UUID, canonical_symbol: str) -> SymbolResolution | None:
        broker = self._brokers.get(broker_id)
        if broker is None:
            return None
        canonical = canonical_symbol.upper()
        for mapping in broker.symbol_mappings:
            if mapping.canonical_symbol.upper() == canonical:
                return SymbolResolution(
                    broker_id=broker_id,
                    canonical_symbol=mapping.canonical_symbol,
                    broker_symbol=mapping.broker_symbol,
                )
        return SymbolResolution(
            broker_id=broker_id,
            canonical_symbol=canonical_symbol,
            broker_symbol=canonical_symbol,
        )

    def fleet_status(self) -> BrokerFleetStatus:
        brokers = list(self._brokers.values())
        accounts = list(self._accounts.values())
        blocked = 0
        recommendations: list[str] = []
        for account in accounts:
            broker = self._brokers[account.broker_id]
            rules = broker.rule_profile
            if account.daily_drawdown_pct >= rules.daily_drawdown_pct or account.total_drawdown_pct >= rules.max_drawdown_pct:
                blocked += 1
                recommendations.append(f"Block new risk on {account.label} pending MASTER Brano review.")
        offline = sum(item.state == ConnectorState.offline for item in brokers)
        degraded = sum(item.state == ConnectorState.degraded for item in brokers)
        if offline:
            recommendations.append("Restore offline read-only broker connectors before relying on fleet totals.")
        if not recommendations:
            recommendations.append("Broker fleet is within configured rule profiles.")
        return BrokerFleetStatus(
            brokers=len(brokers),
            accounts=len(accounts),
            online_brokers=sum(item.state == ConnectorState.online for item in brokers),
            degraded_brokers=degraded,
            offline_brokers=offline,
            blocked_accounts=blocked,
            total_balance=round(sum(item.balance for item in accounts), 2),
            total_equity=round(sum(item.equity for item in accounts), 2),
            recommendations=recommendations,
        )


multi_broker_service = MultiBrokerService()
