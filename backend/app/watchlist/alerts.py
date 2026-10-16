"""Telegram alerts for the watchlist: a price drop, a slide under the 200-day average, the RSI
turning oversold, the price arriving near its 52-week low.

Each fires on the change, not on the state -- the minute it happens, once per symbol and
condition per day -- so a symbol that stays below its average does not send a message every
minute. One push's alerts go out as one message.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.db import SessionLocal
from app.db_models import WatchlistAlertRow

from .models import WatchItem

# A day's drop that is worth a message. Crypto moves more, so its bar is higher.
DROP_PCT = {"Krypto": -5.0}
DROP_PCT_DEFAULT = -3.0
NEAR_LOW = 1.03  # within 3 % of the 52-week low


def _fmt(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def conditions(new: WatchItem, old: WatchItem | None) -> list[tuple[str, str]]:
    """(condition id, text) for every alert this change triggers."""
    if new.price is None:
        return []
    out = []
    drop = DROP_PCT.get(new.category, DROP_PCT_DEFAULT)
    if new.change_pct is not None and new.change_pct <= drop and (old is None or old.change_pct is None or old.change_pct > drop):
        out.append(("drop", f"{_fmt(new.change_pct)} % heute"))
    if (new.vs_sma200_pct is not None and new.vs_sma200_pct < 0
            and old is not None and old.vs_sma200_pct is not None and old.vs_sma200_pct >= 0):
        out.append(("below200", "unter den 200-Tage-Schnitt gefallen"))
    if new.rsi14 is not None and new.rsi14 < 30 and old is not None and old.rsi14 is not None and old.rsi14 >= 30:
        out.append(("oversold", f"RSI {new.rsi14:.0f} – überverkauft"))
    near = lambda i: i.low_52w is not None and i.price is not None and i.price <= i.low_52w * NEAR_LOW
    if near(new) and old is not None and not near(old):
        out.append(("near_low", "nahe am 52-Wochen-Tief"))
    return out


def collect(new_items: list[WatchItem], old_items: list[WatchItem], today: date | None = None) -> list[str]:
    """The lines to send for this push, each condition at most once per symbol and day."""
    today = today or datetime.now(timezone.utc).date()
    old_by_name = {i.name: i for i in old_items}
    lines = []
    with SessionLocal() as session:
        for item in new_items:
            for cond, text in conditions(item, old_by_name.get(item.name)):
                key = f"{today.isoformat()}|{item.name}|{cond}"
                if session.get(WatchlistAlertRow, key) is not None:
                    continue
                session.add(WatchlistAlertRow(key=key, sent_at=datetime.now(timezone.utc)))
                lines.append(f"• {item.name} {_fmt(item.price)}: {text}")
        session.commit()
    return lines


def send(lines: list[str]) -> None:
    """Out through AURON's Telegram bot. A delivery failure must not break the push."""
    if not lines:
        return
    from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError
    try:
        TelegramDeliveryClient().send("Watchlist", "\n".join(lines) + "\n\nBeobachtung, keine Empfehlung.")
    except TelegramDeliveryError:
        pass
