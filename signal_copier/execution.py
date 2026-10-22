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


def _tick(symbol: str):
    """The current quote. A symbol missing from Market Watch has none -- a fresh
    MT5 install shows only a few (#57588 failed on XAUUSD.s that way) -- so it
    is added there first instead of trusting someone did it by hand."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None or not tick.bid:
        mt5.symbol_select(symbol, True)
        for _ in range(100):  # the first quote can take seconds after selecting
            time.sleep(0.1)
            tick = mt5.symbol_info_tick(symbol)
            if tick is not None and tick.bid:
                break
    if tick is None or not tick.bid:
        raise ExecutionError(f"no quote for {symbol}: not in Market Watch and could not be added")
    return tick


def warm_up(symbols: list[str]) -> list[str]:
    """Put the symbols signals usually name into Market Watch at start, so the
    first signal does not wait for its first quote. Returns those added."""
    added = []
    for name in symbols:
        info = mt5.symbol_info(name)
        if info is not None and not info.visible and mt5.symbol_select(name, True):
            added.append(name)
    return added


def connect(allow_live: bool = False, terminal: str | None = None, login: int | None = None) -> None:
    """terminal: path to this profile's terminal64.exe (None: the one that runs).
    login: the account that must be logged in there -- another one is refused."""
    if not (mt5.initialize(path=terminal) if terminal else mt5.initialize()):
        raise ExecutionError(f"MT5 initialize failed ({terminal or 'running terminal'}): {mt5.last_error()}")
    account = mt5.account_info()
    if login and account.login != int(login):
        mt5.shutdown()
        raise ExecutionError(f"MT5 is logged in to {account.login}, this profile is for {login} -- log in there first")
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
    tick = _tick(symbol)
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
    tick = _tick(symbol)
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


def open_manual(symbol: str, side: str, volume: float, sl: float, tp: float) -> Opened:
    """A trade Brano opened by hand from the dashboard's chart: the bot's magic (so the copier sees and can
    close it), comment "hand" -- no signal behind it."""
    tick = _tick(symbol)
    buy = side == "buy"
    result = _send({"action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": volume,
                    "type": mt5.ORDER_TYPE_BUY if buy else mt5.ORDER_TYPE_SELL, "price": tick.ask if buy else tick.bid,
                    "sl": sl, "tp": tp, "deviation": 20, "magic": MAGIC, "comment": "hand", "type_filling": _filling(symbol)})
    filled = mt5.positions_get(ticket=result.order)
    return Opened(result.order, filled[0].price_open if filled else result.price, result.volume)


def cancel_order(order) -> None:
    _send({"action": mt5.TRADE_ACTION_REMOVE, "order": order.ticket})


def digits(symbol: str) -> int:
    return mt5.symbol_info(symbol).digits


def bot_orders() -> list:
    return [o for o in (mt5.orders_get() or []) if o.magic == MAGIC]


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
    info, tick = mt5.symbol_info(symbol), _tick(symbol)
    market = tick.bid if side == "buy" else tick.ask  # the price that would close it
    gap = (market - level) if (side == "buy") == is_sl else (level - market)
    return gap > info.trade_stops_level * info.point


def close_position(position, volume: float | None = None) -> None:
    tick = _tick(position.symbol)
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


def price_at(symbol: str, side: str, ts: float) -> float | None:
    """The quote at a past moment (UTC epoch) -- the first tick at or after it. MT5 keeps tick
    times in server time posing as UTC, so the request is shifted by the server's offset."""
    from datetime import datetime, timezone
    ticks = mt5.copy_ticks_from(symbol, datetime.fromtimestamp(ts + _server_offset_seconds(symbol), timezone.utc),
                                1, mt5.COPY_TICKS_INFO)
    if ticks is None or len(ticks) == 0:
        return None
    t = ticks[0]
    return float(t["ask"] if side == "buy" else t["bid"])


def _server_offset_seconds(symbol: str = "EURUSD") -> int:
    """MT5 stamps deals in server time posing as UTC; this is the gap, to the hour."""
    tick = _tick(symbol)
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


def report_inputs() -> tuple[dict, list[dict], list[dict]]:
    """Account, open positions and every trade deal of the account, as plain dicts for report.build()."""
    a = mt5.account_info()
    account = {"login": a.login, "server": a.server, "currency": a.currency,
               "balance": a.balance, "equity": a.equity}
    positions = [{"ticket": p.ticket, "symbol": p.symbol,
                  "side": "buy" if p.type == mt5.POSITION_TYPE_BUY else "sell",
                  "volume": p.volume, "price_open": p.price_open, "sl": p.sl, "tp": p.tp, "profit": p.profit}
                 for p in mt5.positions_get() or ()]
    offset = _server_offset_seconds()
    closing = (mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_OUT_BY)
    # Deposits and withdrawals are deals too; only buy/sell is trading.
    deals = [{"position_id": d.position_id, "time": d.time - offset, "profit": d.profit,
              "commission": d.commission, "swap": d.swap, "fee": d.fee, "closing": d.entry in closing,
              "symbol": d.symbol, "side": "buy" if d.type == mt5.DEAL_TYPE_BUY else "sell",
              "volume": d.volume, "price": d.price, "comment": d.comment}
             for d in mt5.history_deals_get(datetime(2000, 1, 1), datetime.now() + timedelta(days=1)) or ()
             if d.type in (mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL)]
    return account, positions, deals


def rates(symbol: str, n: int = 240) -> list[list[float]]:
    """The last n five-minute candles as [time (real UTC), open, high, low, close] -- what the dashboard's
    chart draws when Brano clicks a position. MT5 stamps them in server time, like the deals."""
    mt5.symbol_select(symbol, True)
    r = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, n)
    if r is None:
        return []
    off = _server_offset_seconds(symbol)
    return [[int(x["time"]) - off, float(x["open"]), float(x["high"]), float(x["low"]), float(x["close"])] for x in r]


def live_inputs() -> dict:
    """The small, fast part of report_inputs(): balance, equity and each open position's profit --
    two light MT5 calls, read every second for the dashboard's live sums."""
    a = mt5.account_info()
    return {"balance": a.balance, "equity": a.equity,
            "positions": [{"ticket": p.ticket, "profit": p.profit} for p in mt5.positions_get() or ()]}


def spec(symbol: str):
    from signal_copier.sizing import SymbolSpec
    i = mt5.symbol_info(symbol)
    return SymbolSpec(i.trade_tick_size, i.trade_tick_value_loss or i.trade_tick_value,
                      i.volume_min, i.volume_max, i.volume_step)


def pnl_at_sl(symbol: str, side: str, volume: float, entry: float, sl: float) -> float:
    kind = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
    return mt5.order_calc_profit(kind, symbol, volume, entry, sl)
