from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.trading.auron_multi_account_allocation_v21_534 import AccountChildIntent
from app.trading.auron_trading_account_state_v21_531 import (
    NormalizedAccountState,
    NormalizedOrder,
    NormalizedPosition,
    TradingAccountStateStore,
    TradingDayState,
)
from app.trading.auron_trading_guards_v21_535 import GuardDecision
from app.trading.auron_trading_registry_v21_530 import TradingAccountRegistry


class BrokerAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class BrokerAccountSnapshot:
    account_id: str
    balance: float
    equity: float
    floating_pnl: float
    realized_pnl: float
    gross_exposure: float
    net_exposure: float
    margin_used: float
    free_margin: float
    positions: tuple[NormalizedPosition, ...]
    orders: tuple[NormalizedOrder, ...]
    trading_day: TradingDayState
    source: str = 'mt5-read-only'


@dataclass(frozen=True)
class PaperExecution:
    paper_execution_id: str
    child_intent_id: str
    account_id: str
    symbol: str
    side: str
    lot: float
    reference_price: float
    stop_loss: float
    take_profit: float | None
    state: str
    integrity_hash: str
    created_at: str
    external_calls_made: int = 0


class ReadOnlyBrokerSource(Protocol):
    def fetch_account_snapshot(self, account_id: str) -> BrokerAccountSnapshot: ...


class InMemoryReadOnlyBrokerSource:
    """B7 test/reference source. It emulates MT5 read-only data without provider I/O."""

    def __init__(self, snapshots: dict[str, BrokerAccountSnapshot]) -> None:
        self.snapshots = snapshots

    def fetch_account_snapshot(self, account_id: str) -> BrokerAccountSnapshot:
        try:
            return self.snapshots[account_id]
        except KeyError as exc:
            raise BrokerAdapterError(f'broker snapshot unavailable for {account_id}') from exc


class MT5BrokerReadOnlyPaperAdapter:
    """B7 boundary for provider state normalization and risk-gated paper execution.

    This class deliberately has no live-order method. A real MT5 transport can later
    implement ReadOnlyBrokerSource, but B7 only synchronizes account state and records
    simulated executions after B6 guard approval.
    """

    def __init__(
        self,
        db_path: str | Path,
        registry: TradingAccountRegistry,
        states: TradingAccountStateStore,
        source: ReadOnlyBrokerSource,
    ) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.states = states
        self.source = source
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS paper_executions (
                    paper_execution_id TEXT PRIMARY KEY,
                    child_intent_id TEXT UNIQUE NOT NULL,
                    account_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    lot REAL NOT NULL,
                    reference_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL,
                    state TEXT NOT NULL,
                    integrity_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')

    def sync_read_only(self, account_id: str) -> NormalizedAccountState:
        if self.registry.get_account(account_id) is None:
            raise BrokerAdapterError('account must exist in trading registry before broker sync')
        snapshot = self.source.fetch_account_snapshot(account_id)
        if snapshot.account_id != account_id:
            raise BrokerAdapterError('broker snapshot account mismatch')
        normalized = NormalizedAccountState(
            account_id=account_id,
            balance=snapshot.balance,
            equity=snapshot.equity,
            floating_pnl=snapshot.floating_pnl,
            realized_pnl=snapshot.realized_pnl,
            gross_exposure=snapshot.gross_exposure,
            net_exposure=snapshot.net_exposure,
            margin_used=snapshot.margin_used,
            free_margin=snapshot.free_margin,
            positions=snapshot.positions,
            orders=snapshot.orders,
            trading_day=snapshot.trading_day,
            observed_at=datetime.now(timezone.utc).isoformat(),
            source=snapshot.source,
        )
        return self.states.upsert_snapshot(normalized)

    @staticmethod
    def _paper_id(intent: AccountChildIntent) -> str:
        return 'paper:' + hashlib.sha256(intent.child_intent_id.encode()).hexdigest()[:24]

    @staticmethod
    def _hash_payload(intent: AccountChildIntent) -> str:
        payload = {
            'child_intent_id': intent.child_intent_id,
            'account_id': intent.account_id,
            'symbol': intent.symbol,
            'side': intent.side,
            'lot': intent.calculated_lot,
            'reference_price': intent.reference_price,
            'stop_loss': intent.stop_loss,
            'take_profit': intent.take_profit,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def paper_execute(self, intent: AccountChildIntent, guard: GuardDecision) -> PaperExecution:
        if intent.account_id != guard.account_id or intent.child_intent_id != guard.child_intent_id:
            raise BrokerAdapterError('guard decision does not match child intent')
        if intent.state != 'ready-for-guard-evaluation' or intent.blockers:
            raise BrokerAdapterError('child intent is not allocation-ready')
        if guard.state != 'ready-for-paper-execution' or guard.blockers:
            raise BrokerAdapterError('B6 guard approval required for paper execution')
        if intent.calculated_lot <= 0:
            raise BrokerAdapterError('paper execution requires positive calculated lot')

        integrity_hash = self._hash_payload(intent)
        paper_id = self._paper_id(intent)
        with self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM paper_executions WHERE child_intent_id=?',
                (intent.child_intent_id,),
            ).fetchone()
            if row is not None:
                existing = self._row_to_execution(row)
                if existing.integrity_hash != integrity_hash:
                    raise BrokerAdapterError('child intent replay payload mismatch')
                return existing

            created_at = datetime.now(timezone.utc).isoformat()
            conn.execute('''
                INSERT INTO paper_executions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                paper_id, intent.child_intent_id, intent.account_id, intent.symbol, intent.side,
                intent.calculated_lot, intent.reference_price, intent.stop_loss, intent.take_profit,
                'paper-filled', integrity_hash, created_at,
            ))

        result = self.get_paper_execution(intent.child_intent_id)
        if result is None:
            raise BrokerAdapterError('paper execution persistence failed')
        return result

    @staticmethod
    def _row_to_execution(row: sqlite3.Row) -> PaperExecution:
        return PaperExecution(**dict(row), external_calls_made=0)

    def get_paper_execution(self, child_intent_id: str) -> PaperExecution | None:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM paper_executions WHERE child_intent_id=?',
                (child_intent_id,),
            ).fetchone()
        return None if row is None else self._row_to_execution(row)

    def list_paper_executions(self) -> tuple[PaperExecution, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM paper_executions ORDER BY created_at ASC').fetchall()
        return tuple(self._row_to_execution(row) for row in rows)

    @staticmethod
    def live_execution_available() -> bool:
        return False
