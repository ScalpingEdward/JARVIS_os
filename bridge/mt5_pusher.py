"""
AURON MT5 Bridge Pusher
========================

Runs locally, on the same Windows machine as a logged-in MetaTrader 5
terminal. Periodically reads account state, positions, pending orders,
recent deals, ticks, and symbol contract specs via the official
MetaTrader5 Python package, and pushes them to AURON's mt5_bridge
ingest endpoint.

This script is READ-ONLY with respect to MT5: it never calls order_send,
order_check, or anything else that could place, modify, or close a trade.
It only reads. Everything it sends is registered on the AURON side as
read_only=True (mt5_bridge.service refuses to register anything else).

Requirements (install once, on the Windows machine running MT5):
    pip install MetaTrader5 requests

Usage:
    python mt5_pusher.py \\
        --backend-url http://localhost:8000 \\
        --account-login 12345678 \\
        --server "YourBroker-Server" \\
        --broker "YourBroker" \\
        --symbols XAUUSD,EURUSD \\
        --interval 5

Run --help for all options. On first run this registers a new terminal
with AURON and saves the returned terminal_id to --state-file (default:
mt5_bridge_state.json, next to this script) so subsequent runs reuse the
same terminal record instead of registering a new one every time.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import MetaTrader5 as mt5
except ImportError:
    print(
        "The MetaTrader5 package is not installed or not usable on this machine.\n"
        "This script only works on Windows, with a MetaTrader 5 terminal installed.\n"
        "Install it with: pip install MetaTrader5",
        file=sys.stderr,
    )
    raise

try:
    import requests
except ImportError:
    print("Missing dependency. Install it with: pip install requests", file=sys.stderr)
    raise


def _utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class BridgeState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.terminal_id: str | None = None
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.terminal_id = data.get("terminal_id")
            except (json.JSONDecodeError, OSError):
                pass

    def save(self, terminal_id: str) -> None:
        self.terminal_id = terminal_id
        self.path.write_text(json.dumps({"terminal_id": terminal_id}))


class AuronBridgeClient:
    def __init__(self, backend_url: str) -> None:
        self.base = backend_url.rstrip("/") + "/v1/mt5"
        self.session = requests.Session()

    def register(self, *, name: str, terminal_path: str, account_login: int, broker: str, server: str) -> str:
        response = self.session.post(
            f"{self.base}/terminals",
            json={
                "name": name,
                "terminal_path": terminal_path,
                "account_login": account_login,
                "broker": broker,
                "server": server,
                "read_only": True,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["id"]

    def heartbeat(self, terminal_id: str, *, bridge_version: str, latency_ms: int) -> None:
        response = self.session.post(
            f"{self.base}/terminals/{terminal_id}/heartbeat",
            json={"bridge_version": bridge_version, "latency_ms": latency_ms},
            timeout=10,
        )
        response.raise_for_status()

    def ingest(self, terminal_id: str, payload: dict) -> None:
        response = self.session.post(f"{self.base}/terminals/{terminal_id}/snapshot", json=payload, timeout=15)
        response.raise_for_status()


def collect_snapshot(symbols: list[str], deal_history_days: int) -> dict:
    account = mt5.account_info()
    if account is None:
        raise RuntimeError(f"mt5.account_info() failed: {mt5.last_error()}")

    positions = mt5.positions_get() or ()
    pending = mt5.orders_get() or ()

    from_date = datetime.now(timezone.utc).timestamp() - deal_history_days * 86400
    deals = mt5.history_deals_get(from_date, time.time()) or ()

    ticks = []
    symbol_specs = []
    for symbol in symbols:
        info = mt5.symbol_info(symbol)
        if info is None:
            print(f"[warn] {symbol}: not found on this broker (check exact symbol name in Market Watch)", file=sys.stderr)
            continue
        if not info.visible:
            # MT5 only streams ticks for symbols visible in Market Watch --
            # symbol_info_tick() silently returns None otherwise. select it.
            if not mt5.symbol_select(symbol, True):
                print(f"[warn] {symbol}: found but could not add to Market Watch: {mt5.last_error()}", file=sys.stderr)
                continue
            info = mt5.symbol_info(symbol)  # re-fetch now that it's visible

        tick = mt5.symbol_info_tick(symbol)
        if tick is not None:
            ticks.append({"symbol": symbol, "bid": tick.bid, "ask": tick.ask, "last": tick.last, "captured_at": _utc(tick.time)})
        else:
            print(f"[warn] {symbol}: still no tick after selecting -- market may be closed", file=sys.stderr)
        if info is not None:
            symbol_specs.append(
                {
                    "symbol": symbol,
                    "point": info.point,
                    "digits": info.digits,
                    "volume_min": info.volume_min,
                    "volume_max": info.volume_max,
                    "volume_step": info.volume_step,
                    "trade_contract_size": info.trade_contract_size,
                    "trade_tick_size": info.trade_tick_size,
                    "trade_tick_value": info.trade_tick_value,
                }
            )

    return {
        "account": {
            "balance": account.balance,
            "equity": account.equity,
            "margin": account.margin,
            "free_margin": account.margin_free,
            "margin_level": account.margin_level if account.margin_level else None,
            "floating_pnl": account.profit,
            "daily_pnl": 0,  # MT5 does not expose this directly; AURON's accounts registry tracks it separately
            "currency": account.currency,
        },
        "positions": [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "side": "buy" if p.type == mt5.ORDER_TYPE_BUY else "sell",
                "volume": p.volume,
                "open_price": p.price_open,
                "current_price": p.price_current,
                "stop_loss": p.sl or None,
                "take_profit": p.tp or None,
                "profit": p.profit,
                "opened_at": _utc(p.time),
            }
            for p in positions
        ],
        "pending_orders": [
            {
                "ticket": o.ticket,
                "symbol": o.symbol,
                "order_type": str(o.type),
                "volume": o.volume_current,
                "price": o.price_open,
                "stop_loss": o.sl or None,
                "take_profit": o.tp or None,
                "expires_at": _utc(o.time_expiration) if o.time_expiration else None,
            }
            for o in pending
        ],
        "deals": [
            {
                "ticket": d.ticket,
                "order_ticket": d.order or None,
                "symbol": d.symbol,
                "side": "buy" if d.type == mt5.DEAL_TYPE_BUY else "sell",
                "volume": d.volume,
                "price": d.price,
                "profit": d.profit,
                "commission": d.commission,
                "swap": d.swap,
                "executed_at": _utc(d.time),
            }
            for d in deals
        ],
        "ticks": ticks,
        "candles": [],
        "journal": [],
        "symbols": symbol_specs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Push local MT5 terminal data to AURON's mt5_bridge.")
    parser.add_argument("--backend-url", required=True, help="AURON backend base URL, e.g. http://localhost:8000")
    parser.add_argument("--account-login", required=True, type=int)
    parser.add_argument("--server", required=True)
    parser.add_argument("--broker", required=True)
    parser.add_argument("--terminal-name", default="AURON MT5 Bridge")
    parser.add_argument("--terminal-path", default=r"C:\Program Files\MetaTrader 5\terminal64.exe")
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols to push ticks/specs for, e.g. XAUUSD,EURUSD")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between pushes.")
    parser.add_argument("--deal-history-days", type=int, default=7)
    parser.add_argument("--state-file", default="mt5_bridge_state.json")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    if not mt5.initialize():
        print(f"mt5.initialize() failed: {mt5.last_error()}", file=sys.stderr)
        sys.exit(1)

    state = BridgeState(Path(args.state_file))
    client = AuronBridgeClient(args.backend_url)

    if state.terminal_id is None:
        terminal_id = client.register(
            name=args.terminal_name,
            terminal_path=args.terminal_path,
            account_login=args.account_login,
            broker=args.broker,
            server=args.server,
        )
        state.save(terminal_id)
        print(f"Registered new terminal: {terminal_id}")
    else:
        print(f"Reusing existing terminal: {state.terminal_id}")

    print(f"Pushing every {args.interval}s for symbols: {', '.join(symbols)}. Ctrl+C to stop.")
    try:
        while True:
            start = time.monotonic()
            try:
                client.heartbeat(state.terminal_id, bridge_version="1.0.0", latency_ms=0)
                snapshot = collect_snapshot(symbols, args.deal_history_days)
                client.ingest(state.terminal_id, snapshot)
            except requests.RequestException as exc:
                print(f"[warn] push failed, will retry next cycle: {exc}", file=sys.stderr)
            except RuntimeError as exc:
                print(f"[warn] MT5 read failed, will retry next cycle: {exc}", file=sys.stderr)
            elapsed = time.monotonic() - start
            time.sleep(max(0.0, args.interval - elapsed))
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
