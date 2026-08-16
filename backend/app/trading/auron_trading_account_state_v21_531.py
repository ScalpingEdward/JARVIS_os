from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from app.trading.auron_trading_registry_v21_530 import TradingAccountRegistry

PositionSide = Literal['buy', 'sell']
OrderSide = Literal['buy', 'sell']
OrderType = Literal['market', 'limit', 'stop', 'stop-limit']
OrderStatus = Literal['pending', 'partially-filled', 'filled', 'cancelled', 'rejected']


class TradingStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class NormalizedPosition:
    position_id: str
    symbol: str
    side: PositionSide
    volume: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass(frozen=True)
class NormalizedOrder:
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    volume: float
    price: float | None
    status: OrderStatus


@dataclass(frozen=True)
class TradingDayState:
    trading_date: str
    realized_pnl: float
    start_balance: float
    trades_closed: int
    trading_day_counted: bool


@dataclass(frozen=True)
class NormalizedAccountState:
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
    observed_at: str
    source: str


class TradingAccountStateStore:
    """Persistent normalized account-state store.

    B2 accepts normalized snapshots only. It performs no broker/MT5 connection and
    no external calls. Provider adapters added later must translate their native
    state into this schema before risk or allocation logic consumes it.
    """

    def __init__(self, db_path: str | Path, registry: TradingAccountRegistry) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trading_account_state (
                    account_id TEXT PRIMARY KEY,
                    balance REAL NOT NULL,
                    equity REAL NOT NULL,
                    floating_pnl REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    gross_exposure REAL NOT NULL,
                    net_exposure REAL NOT NULL,
                    margin_used REAL NOT NULL,
                    free_margin REAL NOT NULL,
                    trading_date TEXT NOT NULL,
                    trading_day_realized_pnl REAL NOT NULL,
                    trading_day_start_balance REAL NOT NULL,
                    trades_closed INTEGER NOT NULL,
                    trading_day_counted INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    source TEXT NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trading_positions (
                    account_id TEXT NOT NULL,
                    position_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    volume REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    current_price REAL NOT NULL,
                    unrealized_pnl REAL NOT NULL,
                    stop_loss REAL,
                    take_profit REAL,
                    PRIMARY KEY(account_id, position_id)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trading_orders (
                    account_id TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    volume REAL NOT NULL,
                    price REAL,
                    status TEXT NOT NULL,
                    PRIMARY KEY(account_id, order_id)
                )
            ''')

    @staticmethod
    def _validate_snapshot(state: NormalizedAccountState) -> None:
        if state.balance < 0 or state.equity < 0:
            raise TradingStateError('balance and equity cannot be negative')
        if state.margin_used < 0 or state.free_margin < 0:
            raise TradingStateError('margin values cannot be negative')
        if state.gross_exposure < 0:
            raise TradingStateError('gross_exposure cannot be negative')
        if state.trading_day.start_balance < 0:
            raise TradingStateError('trading-day start balance cannot be negative')
        for position in state.positions:
            if position.volume <= 0 or position.entry_price <= 0 or position.current_price <= 0:
                raise TradingStateError('positions require positive volume and prices')
        for order in state.orders:
            if order.volume <= 0:
                raise TradingStateError('orders require positive volume')
            if order.price is not None and order.price <= 0:
                raise TradingStateError('order price must be positive when supplied')

    def upsert_snapshot(self, state: NormalizedAccountState) -> NormalizedAccountState:
        if self.registry.get_account(state.account_id) is None:
            raise TradingStateError('account must exist in B1 registry before state can be stored')
        self._validate_snapshot(state)
        with self._connect() as conn:
            conn.execute('''
                INSERT INTO trading_account_state VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(account_id) DO UPDATE SET
                    balance=excluded.balance,equity=excluded.equity,floating_pnl=excluded.floating_pnl,
                    realized_pnl=excluded.realized_pnl,gross_exposure=excluded.gross_exposure,
                    net_exposure=excluded.net_exposure,margin_used=excluded.margin_used,free_margin=excluded.free_margin,
                    trading_date=excluded.trading_date,trading_day_realized_pnl=excluded.trading_day_realized_pnl,
                    trading_day_start_balance=excluded.trading_day_start_balance,trades_closed=excluded.trades_closed,
                    trading_day_counted=excluded.trading_day_counted,observed_at=excluded.observed_at,source=excluded.source
            ''', (
                state.account_id,state.balance,state.equity,state.floating_pnl,state.realized_pnl,
                state.gross_exposure,state.net_exposure,state.margin_used,state.free_margin,
                state.trading_day.trading_date,state.trading_day.realized_pnl,state.trading_day.start_balance,
                state.trading_day.trades_closed,int(state.trading_day.trading_day_counted),state.observed_at,state.source,
            ))
            conn.execute('DELETE FROM trading_positions WHERE account_id=?', (state.account_id,))
            conn.execute('DELETE FROM trading_orders WHERE account_id=?', (state.account_id,))
            conn.executemany('''
                INSERT INTO trading_positions VALUES (?,?,?,?,?,?,?,?,?,?)
            ''', [(
                state.account_id,p.position_id,p.symbol,p.side,p.volume,p.entry_price,p.current_price,
                p.unrealized_pnl,p.stop_loss,p.take_profit,
            ) for p in state.positions])
            conn.executemany('''
                INSERT INTO trading_orders VALUES (?,?,?,?,?,?,?,?)
            ''', [(
                state.account_id,o.order_id,o.symbol,o.side,o.order_type,o.volume,o.price,o.status,
            ) for o in state.orders])
        result = self.get_snapshot(state.account_id)
        if result is None:
            raise TradingStateError('snapshot persistence failed')
        return result

    def get_snapshot(self, account_id: str) -> NormalizedAccountState | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM trading_account_state WHERE account_id=?', (account_id,)).fetchone()
            if row is None:
                return None
            positions = conn.execute('SELECT * FROM trading_positions WHERE account_id=? ORDER BY position_id', (account_id,)).fetchall()
            orders = conn.execute('SELECT * FROM trading_orders WHERE account_id=? ORDER BY order_id', (account_id,)).fetchall()
        data = dict(row)
        day = TradingDayState(
            trading_date=data.pop('trading_date'),
            realized_pnl=data.pop('trading_day_realized_pnl'),
            start_balance=data.pop('trading_day_start_balance'),
            trades_closed=data.pop('trades_closed'),
            trading_day_counted=bool(data.pop('trading_day_counted')),
        )
        pos = tuple(NormalizedPosition(**{k:v for k,v in dict(r).items() if k != 'account_id'}) for r in positions)
        ords = tuple(NormalizedOrder(**{k:v for k,v in dict(r).items() if k != 'account_id'}) for r in orders)
        return NormalizedAccountState(**data, positions=pos, orders=ords, trading_day=day)

    def list_snapshots(self) -> list[NormalizedAccountState]:
        with self._connect() as conn:
            ids = [r['account_id'] for r in conn.execute('SELECT account_id FROM trading_account_state ORDER BY account_id').fetchall()]
        return [state for account_id in ids if (state := self.get_snapshot(account_id)) is not None]


def make_manual_snapshot(
    *, account_id: str, balance: float, equity: float, floating_pnl: float, realized_pnl: float,
    gross_exposure: float = 0.0, net_exposure: float = 0.0, margin_used: float = 0.0,
    free_margin: float | None = None, positions: tuple[NormalizedPosition, ...] = (),
    orders: tuple[NormalizedOrder, ...] = (), trading_date: str | None = None,
    trading_day_realized_pnl: float = 0.0, trading_day_start_balance: float | None = None,
    trades_closed: int = 0, trading_day_counted: bool = False,
) -> NormalizedAccountState:
    """Convenience constructor for manual/paper snapshots before B7 provider sync exists."""
    day = trading_date or date.today().isoformat()
    return NormalizedAccountState(
        account_id=account_id,
        balance=balance,
        equity=equity,
        floating_pnl=floating_pnl,
        realized_pnl=realized_pnl,
        gross_exposure=gross_exposure,
        net_exposure=net_exposure,
        margin_used=margin_used,
        free_margin=balance if free_margin is None else free_margin,
        positions=positions,
        orders=orders,
        trading_day=TradingDayState(day, trading_day_realized_pnl, balance if trading_day_start_balance is None else trading_day_start_balance, trades_closed, trading_day_counted),
        observed_at=datetime.now(timezone.utc).isoformat(),
        source='manual-paper',
    )
