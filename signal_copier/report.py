"""What a profile has earned, per Telegram group -- the status AURON shows.

Pure: account, positions and deals come in as plain dicts (execution.py reads
them from MT5), the book says which position belongs to which signal and so
to which group. Every position the copier opened is in the book under its
ticket, and MT5's deal.position_id is that same ticket. Anything else on the
account (a trade by hand) is counted under OTHER, not dropped: the account
total has to add up.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import unicodedata
from datetime import datetime, timedelta, timezone

from signal_copier.book import Book
from signal_copier.risk import day_start

OTHER = "(not from a signal)"
CLOSED_KEEP = 150  # newest closed trades sent along -- the dashboard's history, not an archive


@dataclass
class GroupStatus:
    name: str
    pnl_today: float = 0.0
    pnl_week: float = 0.0
    pnl_total: float = 0.0
    closed_trades: int = 0
    open_positions: int = 0
    open_pnl: float = 0.0


@dataclass
class Status:
    profile: str
    account_login: int
    server: str
    currency: str
    balance: float
    equity: float
    captured_at: str
    groups: list[GroupStatus] = field(default_factory=list)
    open_positions: list[dict] = field(default_factory=list)
    label: str = ""  # what people call this account -- its group's name, not the folder name
    closed: list[dict] = field(default_factory=list)  # newest first, see closed_trades()

    def to_json(self) -> dict:
        return asdict(self)


def display_name(raw: str) -> str:
    """A Telegram title without its decoration: emojis and symbols out, spaces tidied.
    "✨ICT CRT PREMIUM (lifetime + monthly)✨" -> "ICT CRT PREMIUM (lifetime + monthly)"."""
    # "So" is emojis and pictographs; "+" and other maths/currency signs stay.
    kept = "".join(ch for ch in raw if unicodedata.category(ch) != "So" and ch not in "️‍")
    return " ".join(kept.split())


def week_start(now: datetime) -> datetime:
    """Monday midnight, Prague -- the same clock the daily loss stop runs on."""
    today = day_start(now)
    return today - timedelta(days=today.weekday())


def group_of_ticket(book: Book, chat_names: dict[int, str]) -> dict[int, str]:
    out = {}
    for s in book.signals.values():
        name = chat_names.get(s.chat_id, str(s.chat_id))
        for ticket in s.legs.values():
            out[ticket] = name
    return out


def closed_trades(deals: list[dict], owner: dict[int, str], keep: int = CLOSED_KEEP) -> list[dict]:
    """One row per closing deal: when, what, entry and exit, why, what it made.

    A position closed in parts (close half) gives a row per part. The opening deal's
    commission is added to the position's first closing row, so the rows add up to
    what the account really made. side is the position's, the opposite of the
    closing deal's own direction."""
    opening = {d["position_id"]: d for d in deals if not d["closing"]}
    rows, charged = [], set()
    for d in sorted((d for d in deals if d["closing"]), key=lambda d: d["time"]):
        pid = d["position_id"]
        o = opening.get(pid, {})
        amount = d["profit"] + d["commission"] + d["swap"] + d["fee"]
        if pid not in charged:
            amount += o.get("commission", 0) + o.get("swap", 0) + o.get("fee", 0)
            charged.add(pid)
        side = d.get("side")
        rows.append({"position": pid, "group": owner.get(pid, OTHER), "symbol": d.get("symbol", ""),
                     "side": {"buy": "sell", "sell": "buy"}.get(side, side or ""), "volume": d.get("volume", 0),
                     "price_open": o.get("price", 0), "price_close": d.get("price", 0),
                     "opened": o.get("time"), "closed": d["time"], "comment": d.get("comment", ""),
                     "profit": round(amount, 2)})
    return rows[::-1][:keep]


def build(profile: str, account: dict, positions: list[dict], deals: list[dict],
          book: Book, chat_names: dict[int, str], now: datetime | None = None, label: str = "") -> Status:
    """account: login, server, currency, balance, equity.
    positions: ticket, symbol, side, volume, price_open, sl, tp, profit.
    deals: position_id, time (UTC epoch, real), profit, commission, swap, fee, closing (bool)."""
    now = now or datetime.now(timezone.utc)
    today, week = day_start(now).timestamp(), week_start(now).timestamp()
    owner = group_of_ticket(book, chat_names)
    groups: dict[str, GroupStatus] = {name: GroupStatus(name) for name in chat_names.values()}

    def g(ticket: int) -> GroupStatus:
        name = owner.get(ticket, OTHER)
        return groups.setdefault(name, GroupStatus(name))

    for d in deals:
        amount = d["profit"] + d["commission"] + d["swap"] + d["fee"]
        grp = g(d["position_id"])
        grp.pnl_total += amount
        if d["time"] >= week:
            grp.pnl_week += amount
        if d["time"] >= today:
            grp.pnl_today += amount
        if d["closing"]:
            grp.closed_trades += 1

    open_list = []
    for p in positions:
        grp = g(p["ticket"])
        grp.open_positions += 1
        grp.open_pnl += p["profit"]
        open_list.append({**p, "group": grp.name})

    for grp in groups.values():
        for f in ("pnl_today", "pnl_week", "pnl_total", "open_pnl"):
            setattr(grp, f, round(getattr(grp, f), 2))
    ordered = sorted(groups.values(), key=lambda x: (x.name == OTHER, x.name))
    # A by-hand bucket with nothing in it is noise on the dashboard.
    ordered = [x for x in ordered if x.name != OTHER or x.closed_trades or x.open_positions or x.pnl_total]
    return Status(profile, account["login"], account["server"], account["currency"],
                  round(account["balance"], 2), round(account["equity"], 2),
                  now.isoformat(), ordered, open_list, label or profile, closed_trades(deals, owner))
