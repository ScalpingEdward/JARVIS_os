"""A dedicated account that follows the watched insiders -- the scaffold (2026-10-19).

Every new BUY of a watched insider becomes an order intent: which stock (the MT5 symbol the
backtest found at the broker), long, how long to hold (60 trading days -- the horizon the
7-year backtest found worth it), how much risk. Sales are not traded: shorting them lost money
over the backtest (backtest.FOLLOW_CODES).

Nothing is sent anywhere. The account is "nicht verbunden" until it is set up on the VPS; until
then intents only collect, so the list shows what would have been traded.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.db import SessionLocal
from app.db_models import AppSettingRow

CONFIG_KEY = "insider_account.config"
INTENTS_KEY = "insider_account.intents"
DEFAULT = {"connected": False, "label": "Insider-Konto", "risk_pct": 0.5, "hold_trading_days": 60, "follow": "buys"}


def _read(key: str, default):
    with SessionLocal() as s:
        row = s.get(AppSettingRow, key)
    return json.loads(row.value) if row else default


def _write(key: str, value) -> None:
    with SessionLocal() as s:
        s.merge(AppSettingRow(key=key, value=json.dumps(value, ensure_ascii=False), updated_at=datetime.now(timezone.utc)))
        s.commit()


def config() -> dict:
    return {**DEFAULT, **_read(CONFIG_KEY, {})}


def intents() -> list[dict]:
    return _read(INTENTS_KEY, [])


def on_trade(trade: dict, mt5_symbol: str | None, record_note: str) -> dict | None:
    """A watched insider traded. A buy becomes an intent; a sale does not."""
    if trade.get("code") != "P":
        return None
    cfg = config()
    intent = {
        "at": datetime.now(timezone.utc).isoformat(),
        "owner": trade["owner"], "ticker": trade["ticker"], "mt5_symbol": mt5_symbol,
        "side": "buy", "insider_value": trade.get("value"), "insider_price": trade.get("price"),
        "risk_pct": cfg["risk_pct"], "hold_trading_days": cfg["hold_trading_days"], "record": record_note,
        "status": "vorgemerkt" if cfg["connected"] and mt5_symbol else
                  ("kein Symbol beim Broker" if not mt5_symbol else "nicht verbunden"),
    }
    items = intents()
    if any(i["owner"] == intent["owner"] and i["ticker"] == intent["ticker"] and i["at"][:10] == intent["at"][:10] for i in items):
        return None   # the same insider, same stock, same day: one intent
    items.insert(0, intent)
    _write(INTENTS_KEY, items[:200])
    return intent
