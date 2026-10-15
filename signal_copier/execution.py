"""Orders against a running MT5 terminal: open, stop to breakeven, close.

Every position carries MAGIC and a comment with the Telegram message id, so a
reply to that message finds its positions again -- also after a restart.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5

from signal_copier.risk import AccountState, day_start

MAGIC = 26101400

# symbol_info().filling_mode bits; MQL5 defines them, the Python package does not.
SYMBOL_FILLING_FOK = 1
SYMBOL_FILLING_IOC = 2


class ExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Opened:
    ticket: int
    price: float
    volume: float


def connect(allow_live: bool = False) -> None:
    if not mt5.initialize():
        raise ExecutionError(f"MT5 initialize failed: {mt5.last_error()}")
    account = mt5.account_info()
    if account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO and not allow_live:
        mt5.shutdown()
        raise ExecutionError(f"{account.server} is not a demo account; pass allow_live=True deliberately")
    if not mt5.terminal_info().trade_allowed:
        raise ExecutionError("Algo Trading is switched off in the terminal")


def account_id() -> str:
    """'<login>@<server>': which account the terminal is logged in to right now."""
    a = mt5.account_info()
    return f"{a.login}@{a.server}"


def tradable_symbols() -> list[str]:
    """Names that take orders -- quote-only twins are left out (see symbols.py)."""
    return [s.name for s in mt5.symbols_get() if s.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL]


def price(symbol: str, side: str) -> float:
    """What a new position on this side would pay now: ask for a buy, bid for a sell."""
    tick = mt5.symbol_info_tick(symbol)
    return tick.ask if side == "buy" else tick.bid


def _filling(symbol: str) -> int:
    mode = mt5.symbol_info(symbol).filling_mode
    if mode & SYMBOL_FILLING_IOC:
        return mt5.ORDER_FILLING_IOC
    if mode & SYMBOL_FILLING_FOK:
        return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def _send(request: dict) -> mt5.OrderSendResult:
    result = mt5.order_send(request)
    if result is None:
        raise ExecutionError(f"order_send returned nothing: {mt5.last_error()}")
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise ExecutionError(f"retcode {result.retcode}: {result.comment}")
    return result


def open_position(symbol: str, side: str, volume: float, sl: float, tp: float, signal_id: int, leg: int = 1) -> Opened:
    tick = mt5.symbol_info_tick(symbol)
    buy = side == "buy"
    result = _send({
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if buy else mt5.ORDER_TYPE_SELL,
        "price": tick.ask if buy else tick.bid,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": MAGIC,
        "comment": f"sig:{signal_id}:{leg}",
        "type_filling": _filling(symbol),
    })
    # FTMO answers with price 0.0; the position itself knows the real fill.
    filled = mt5.positions_get(ticket=result.order)
    price = filled[0].price_open if filled else result.price
    return Opened(result.order, price, result.volume)


def bot_positions() -> list:
    return [p for p in (mt5.positions_get() or []) if p.magic == MAGIC]


def positions_for(signal_id: int) -> list:
    return [p for p in bot_positions() if p.comment.startswith(f"sig:{signal_id}:")]


def position(ticket: int):
    found = mt5.positions_get(ticket=ticket)
    return found[0] if found else None


def set_sltp(position, sl: float | None = None, tp: float | None = None) -> None:
    _send({
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": position.symbol,
        "position": position.ticket,
        "sl": position.sl if sl is None else sl,
        "tp": position.tp if tp is None else tp,
        "magic": MAGIC,
    })


def move_sl_to_breakeven(position) -> None:
    set_sltp(position, sl=position.price_open)


def stop_distance_ok(symbol: str, level: float, side: str, is_sl: bool) -> bool:
    """Broker's minimum distance (stops_level, in points) between price and a new SL/TP."""
    info, tick = mt5.symbol_info(symbol), mt5.symbol_info_tick(symbol)
    market = tick.bid if side == "buy" else tick.ask  # the price that would close it
    gap = (market - level) if (side == "buy") == is_sl else (level - market)
    return gap > info.trade_stops_level * info.point


def close_position(position, volume: float | None = None) -> None:
    tick = mt5.symbol_info_tick(position.symbol)
    buy = position.type == mt5.POSITION_TYPE_BUY
    _send({
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "position": position.ticket,
        "volume": position.volume if volume is None else volume,
        "type": mt5.ORDER_TYPE_SELL if buy else mt5.ORDER_TYPE_BUY,
        "price": tick.bid if buy else tick.ask,
        "deviation": 20,
        "magic": MAGIC,
        "type_filling": _filling(position.symbol),
    })


def _server_offset_seconds(symbol: str = "EURUSD") -> int:
    """MT5 stamps deals in server time posing as UTC; this is the gap, to the hour."""
    tick = mt5.symbol_info_tick(symbol)
    return round((tick.time - time.time()) / 3600) * 3600


def account_state(initial_balance: float) -> AccountState:
    account = mt5.account_info()
    offset = _server_offset_seconds()
    since = day_start(datetime.now(timezone.utc)).timestamp()
    # Fetch generously and filter on our side: the from/to arguments suffer the
    # same server-time confusion as the deal stamps.
    deals = mt5.history_deals_get(datetime.now() - timedelta(days=3), datetime.now() + timedelta(days=1)) or ()
    today = sum(d.profit + d.commission + d.swap + d.fee for d in deals
                if d.type in (mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL) and d.time - offset >= since)

    pnl_at_sl = []
    for p in mt5.positions_get() or ():
        if not p.sl:
            pnl_at_sl.append(None)
            continue
        kind = mt5.ORDER_TYPE_BUY if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_SELL
        pnl_at_sl.append(mt5.order_calc_profit(kind, p.symbol, p.volume, p.price_open, p.sl))
    return AccountState(initial_balance, account.balance - today, account.balance, account.equity, tuple(pnl_at_sl))


def spec(symbol: str):
    from signal_copier.sizing import SymbolSpec
    i = mt5.symbol_info(symbol)
    return SymbolSpec(i.trade_tick_size, i.trade_tick_value_loss or i.trade_tick_value,
                      i.volume_min, i.volume_max, i.volume_step)


def pnl_at_sl(symbol: str, side: str, volume: float, entry: float, sl: float) -> float:
    kind = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
    return mt5.order_calc_profit(kind, symbol, volume, entry, sl)
