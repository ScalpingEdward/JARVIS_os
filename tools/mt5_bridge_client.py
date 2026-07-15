"""Local Windows/VPS MT5 reader for PHOENIX.

Requires: pip install MetaTrader5 requests
The terminal must already be logged in. No trading functions are used.
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone
from typing import Any

import requests

try:
    import MetaTrader5 as mt5
except ImportError as exc:  # pragma: no cover - Windows runtime dependency
    raise SystemExit("Install the MetaTrader5 package: pip install MetaTrader5 requests") from exc


def iso_from_epoch(value: int) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def position_payload(item: Any) -> dict[str, Any]:
    return {
        "ticket": item.ticket,
        "symbol": item.symbol,
        "side": "buy" if item.type == mt5.POSITION_TYPE_BUY else "sell",
        "volume": item.volume,
        "open_price": item.price_open,
        "current_price": item.price_current,
        "stop_loss": item.sl or None,
        "take_profit": item.tp or None,
        "profit": item.profit,
        "opened_at": iso_from_epoch(item.time),
    }


def order_payload(item: Any) -> dict[str, Any]:
    return {
        "ticket": item.ticket,
        "symbol": item.symbol,
        "order_type": str(item.type),
        "volume": item.volume_current,
        "price": item.price_open,
        "stop_loss": item.sl or None,
        "take_profit": item.tp or None,
        "expires_at": iso_from_epoch(item.time_expiration) if item.time_expiration else None,
    }


def account_payload() -> dict[str, Any]:
    account = mt5.account_info()
    if account is None:
        raise RuntimeError(f"MT5 account unavailable: {mt5.last_error()}")
    return {
        "balance": account.balance,
        "equity": account.equity,
        "margin": account.margin,
        "free_margin": account.margin_free,
        "margin_level": account.margin_level or None,
        "floating_pnl": account.profit,
        "daily_pnl": 0,
        "currency": account.currency,
    }


def snapshot() -> dict[str, Any]:
    return {
        "account": account_payload(),
        "positions": [position_payload(item) for item in (mt5.positions_get() or [])],
        "pending_orders": [order_payload(item) for item in (mt5.orders_get() or [])],
        "deals": [],
        "ticks": [],
        "candles": [],
        "journal": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="PHOENIX read-only MT5 bridge")
    parser.add_argument("--api", default=os.getenv("PHOENIX_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--terminal-id", default=os.getenv("PHOENIX_MT5_TERMINAL_ID"))
    parser.add_argument("--terminal-path", default=os.getenv("MT5_TERMINAL_PATH"))
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()
    if not args.terminal_id:
        raise SystemExit("Set --terminal-id or PHOENIX_MT5_TERMINAL_ID")
    if not mt5.initialize(path=args.terminal_path or None):
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    base = args.api.rstrip("/")
    try:
        while True:
            requests.post(
                f"{base}/v1/mt5/terminals/{args.terminal_id}/heartbeat",
                json={"bridge_version": "2.1.0", "latency_ms": 0},
                timeout=10,
            ).raise_for_status()
            requests.post(
                f"{base}/v1/mt5/terminals/{args.terminal_id}/snapshot",
                json=snapshot(),
                timeout=20,
            ).raise_for_status()
            time.sleep(max(2, args.interval))
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
