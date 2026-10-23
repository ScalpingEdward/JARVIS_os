"""A trade AURON prepares and opens on Brano's word (Brano, 2026-10-23: "prepare gold with lots, risk, TPs --
and when I say open, open it").

prepare  symbol, side, stop, one or more targets, risk in % (or lots) -> the copier's MT5 gives price and
         contract data, the lots are worked out for the risk (rounded down, like the copier's sizing), split
         over the targets (one position per TP). One ticket at a time; a new one replaces the old.
open     only on Brano's own order: his click on the ticket card, or his own last words in the dashboard or
         the app ("eröffne jetzt") -- checked here, not left to AURON. Never over Telegram. Right after AURON
         read a mail or the web, a spoken order is not enough: the card asks for his click. Limits: at most
         MAX_LOTS in all and MAX_RISK_PCT; the copier itself refuses while trading is stopped.
"""
from __future__ import annotations

import math
import re
import time

MAX_LOTS = 1.0
MAX_RISK_PCT = 2.0
TICKET_FOR_S = 15 * 60
# "eröffne jetzt", "open it", "platzier den Trade", "führ aus" -- a plain "öffne" only with the trade in it
# ("öffne den Chart" must never open a position)
OPEN_WORDS = re.compile(r"\beröffne|\bopen\b|\bplatzier|\bausführen\b|\bführ\w*( \w+)? aus\b"
                        r"|\böffne\b.*\b(trade|position|ticket|jetzt|ihn)\b", re.I)

_ticket: dict | None = None
_seq = 0


class TicketError(ValueError):
    pass


def _account(account: str | None):
    from app.copier_status.service import copier_status_service
    accs = [a for a in copier_status_service.overview().accounts if a.state == "live"] or copier_status_service.overview().accounts
    if not accs:
        raise TicketError("kein Kopierer meldet sich -- ohne MT5 kein Trade")
    if account:
        n = account.lower()
        hit = [a for a in accs if n in a.profile.lower() or n in (a.label or "").lower()]
        if not hit:
            raise TicketError(f"kein Konto {account!r}; es gibt {[a.label or a.profile for a in accs]}")
        return hit[0]
    return accs[0]


def _quote(profile: str, symbol: str, wait_s: float = 12) -> dict:
    from app.copier_status import api
    key, end = api.want_quote(profile, symbol), time.time() + wait_s
    while time.time() < end:
        q = api.quote_for(profile, key)
        if q:
            if q.get("error"):
                raise TicketError(f"MT5 kennt {symbol!r} nicht: {q['error']}")
            return q
        time.sleep(0.3)
    raise TicketError("der Kopierer hat keinen Kurs geschickt -- läuft er?")


def lots_for(balance: float, risk_pct: float, entry: float, sl: float, q: dict) -> float:
    """Largest lot size whose loss at the stop stays within the risk -- rounded down to the volume step."""
    per_lot = abs(entry - sl) / q["tick_size"] * q["tick_value"]
    if per_lot <= 0:
        raise TicketError("Stop gleich Einstieg -- so lässt sich kein Risiko rechnen")
    raw = balance * risk_pct / 100 / per_lot
    step = q["vol_step"] or 0.01
    return round(math.floor(raw / step + 1e-9) * step, 2)


def prepare(symbol: str, side: str, sl: float, tps: list[float], risk_pct: float | None = None, lots: float | None = None,
            account: str | None = None) -> dict:
    global _ticket, _seq
    side = side.lower()
    if side not in ("buy", "sell"):
        raise TicketError("Richtung buy oder sell")
    tps = [float(t) for t in (tps or [])][:4]
    a = _account(account)
    from app.dashboard_layout.ui import _symbol
    q = _quote(a.profile, _symbol(symbol))
    entry = q["ask"] if side == "buy" else q["bid"]
    sign = 1 if side == "buy" else -1
    if sl and (entry - sl) * sign <= 0:
        raise TicketError(f"der Stop {sl} liegt auf der falschen Seite des Kurses {entry}")
    for t in tps:
        if (t - entry) * sign <= 0:
            raise TicketError(f"das Ziel {t} liegt auf der falschen Seite des Kurses {entry}")
    if lots is None:
        if not sl:
            raise TicketError("ohne Stop kein Risiko-Lot -- Stop oder feste Lots angeben")
        risk_pct = float(risk_pct or 1.0)
        if risk_pct > MAX_RISK_PCT:
            raise TicketError(f"{risk_pct} % ist über der Grenze von {MAX_RISK_PCT} %")
        lots = lots_for(a.balance, risk_pct, entry, sl, q)
    lots = round(float(lots), 2)
    if lots > MAX_LOTS:
        raise TicketError(f"{lots} Lots sind über der Grenze von {MAX_LOTS}")
    n = max(1, len(tps))
    step = q["vol_step"] or 0.01
    each = math.floor(lots / n / step + 1e-9) * step
    if each < q["vol_min"]:
        n, each = 1, lots                              # too small to split: one position, the first target
    if lots < q["vol_min"]:
        raise TicketError(f"{lots} Lots sind unter dem Minimum {q['vol_min']} -- Risiko zu klein für diesen Stop")
    legs = [{"lots": round(each, 2), "tp": tps[i] if i < len(tps) else 0} for i in range(n)]
    legs[-1]["lots"] = round(lots - each * (n - 1), 2)  # the rest goes to the last
    per_lot = abs(entry - sl) / q["tick_size"] * q["tick_value"] if sl else 0
    _seq += 1
    _ticket = {"id": _seq, "profile": a.profile, "account": a.label or a.profile, "currency": a.currency, "symbol": q["symbol"],
               "side": side, "entry": entry, "sl": sl or 0, "tps": tps, "lots": lots, "legs": legs,
               "risk_money": round(per_lot * lots, 2), "risk_pct": round(per_lot * lots / a.balance * 100, 2) if a.balance else None,
               "rr": [round(abs(t - entry) / abs(entry - sl), 2) for t in tps] if sl else [],
               "created": time.time(), "status": "ready"}
    return dict(_ticket)


def active() -> dict | None:
    if _ticket and _ticket["status"] == "ready" and time.time() - _ticket["created"] > TICKET_FOR_S:
        _ticket["status"] = "expired"
    return dict(_ticket) if _ticket else None


def cancel() -> dict:
    t = active()
    if not t or t["status"] != "ready":
        raise TicketError("kein offenes Ticket")
    _ticket["status"] = "cancelled"
    return dict(_ticket)


def open_ticket(by: str, said: str = "", channel: str = "dashboard", external_read: bool = False) -> dict:
    """by: "click" (his click on the card) or "word" (AURON, on Brano's own last words -- checked here)."""
    t = active()
    if not t or t["status"] != "ready":
        raise TicketError("kein offenes Ticket -- erst vorbereiten" if not t or t["status"] != "expired" else "das Ticket ist abgelaufen -- neu vorbereiten")
    if by != "click":
        if channel == "telegram":
            raise TicketError("über Telegram werden keine Trades eröffnet -- im Dashboard oder in der App")
        if not OPEN_WORDS.search(said or ""):
            raise TicketError("Brano hat nicht gesagt, dass eröffnet werden soll -- nur auf seinen ausdrücklichen Befehl")
        if external_read:
            _ticket["status"] = "ready"
            return {**dict(_ticket), "waiting_for_click": "AURON hat eben eine Mail oder Webseite gelesen -- eröffnen nur per Klick auf das Ticket"}
    from app.copier_status import commands
    sent = []
    for leg in t["legs"]:
        action = f"open:{t['symbol']}:{t['side']}:{leg['lots']}:{t['sl'] or ''}:{leg['tp'] or ''}"
        sent.append(commands.create(t["profile"], action, "auron" if by == "word" else "dashboard", confirmed=True)["id"])
    _ticket.update(status="sent", sent=sent, sent_at=time.time(), by=by)
    return dict(_ticket)
