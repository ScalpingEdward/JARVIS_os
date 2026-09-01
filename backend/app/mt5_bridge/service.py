from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import (
    MT5BridgeStatus,
    MT5ConnectionState,
    MT5Heartbeat,
    MT5SnapshotIngest,
    MT5TerminalData,
    MT5TerminalRecord,
    MT5TerminalRegister,
)


class MT5BridgeError(ValueError):
    pass


class MT5BridgeService:
    """Stores data pushed by local MT5 bridge processes. No trade methods exist."""

    stale_after = timedelta(seconds=30)
    disconnect_after = timedelta(minutes=2)

    def __init__(self) -> None:
        self._items: dict[UUID, MT5TerminalData] = {}

    def reset(self) -> None:
        self._items.clear()

    def register(self, payload: MT5TerminalRegister) -> MT5TerminalRecord:
        if payload.read_only is not True:
            raise MT5BridgeError("MT5 bridge must be registered in read-only mode")
        if any(item.terminal.account_login == payload.account_login and item.terminal.server == payload.server for item in self._items.values()):
            raise MT5BridgeError("MT5 terminal is already registered")
        terminal = MT5TerminalRecord(**payload.model_dump())
        self._items[terminal.id] = MT5TerminalData(terminal=terminal)
        return deepcopy(terminal)

    def heartbeat(self, terminal_id: UUID, payload: MT5Heartbeat) -> MT5TerminalRecord:
        data = self._require(terminal_id)
        data.terminal.last_heartbeat_at = datetime.now(timezone.utc)
        data.terminal.bridge_version = payload.bridge_version
        data.terminal.latency_ms = payload.latency_ms
        data.terminal.state = MT5ConnectionState.connected
        return deepcopy(data.terminal)

    def ingest(self, terminal_id: UUID, payload: MT5SnapshotIngest) -> MT5TerminalData:
        data = self._require(terminal_id)
        if data.terminal.read_only is not True:
            raise MT5BridgeError("Read-only safety contract is not active")
        data.account = payload.account
        data.positions = payload.positions
        data.pending_orders = payload.pending_orders
        data.deals = payload.deals[-1000:]
        data.ticks = payload.ticks[-500:]
        data.candles = payload.candles[-5000:]
        data.journal = payload.journal[-1000:]
        if payload.symbols:
            # Specs rarely change; replace by symbol rather than accumulating
            # or dropping older entries the way the rolling lists above do.
            by_symbol = {spec.symbol: spec for spec in data.symbols}
            for spec in payload.symbols:
                by_symbol[spec.symbol] = spec
            data.symbols = list(by_symbol.values())
        data.terminal.last_heartbeat_at = datetime.now(timezone.utc)
        data.terminal.state = MT5ConnectionState.connected
        return deepcopy(data)

    def get(self, terminal_id: UUID) -> MT5TerminalData:
        self.refresh_states()
        return deepcopy(self._require(terminal_id))

    def list(self) -> list[MT5TerminalData]:
        self.refresh_states()
        return [deepcopy(item) for item in self._items.values()]

    def status(self) -> MT5BridgeStatus:
        self.refresh_states()
        states = [item.terminal.state for item in self._items.values()]
        return MT5BridgeStatus(
            terminals=len(states),
            connected=states.count(MT5ConnectionState.connected),
            stale=states.count(MT5ConnectionState.stale),
            disconnected=states.count(MT5ConnectionState.disconnected),
        )

    def refresh_states(self, now: datetime | None = None) -> None:
        current = now or datetime.now(timezone.utc)
        for data in self._items.values():
            heartbeat = data.terminal.last_heartbeat_at
            if heartbeat is None or current - heartbeat >= self.disconnect_after:
                data.terminal.state = MT5ConnectionState.disconnected
            elif current - heartbeat >= self.stale_after:
                data.terminal.state = MT5ConnectionState.stale
            else:
                data.terminal.state = MT5ConnectionState.connected

    def _require(self, terminal_id: UUID) -> MT5TerminalData:
        item = self._items.get(terminal_id)
        if item is None:
            raise MT5BridgeError("MT5 terminal not found")
        return item


mt5_bridge_service = MT5BridgeService()
