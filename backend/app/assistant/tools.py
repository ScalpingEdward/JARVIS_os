"""What AURON can look at while he answers.

Every tool here only reads. Nothing in this file opens, closes or posts anything --
when an acting tool comes (answering a mail, closing a trade), it gets its own
confirmation step, not a line in this list.
"""
from __future__ import annotations

import json
from collections.abc import Callable

# Anthropic runs this one itself; no key of ours, no Tavily needed.
WEB_SEARCH = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}


def _trading() -> dict:
    from app.copier_status.service import copier_status_service
    o = copier_status_service.overview()
    return {
        "totals": [t.model_dump() for t in o.totals],
        "accounts": [{"name": a.label or a.profile, "state": a.state, "currency": a.currency,
                      "balance": a.balance, "equity": a.equity,
                      "open": [p.model_dump() for p in a.open_positions]} for a in o.accounts],
        "groups": [g.model_dump() for g in o.groups],
    }


def _watchlist(name: str | None = None) -> dict:
    from app.watchlist.service import watchlist_service
    w = watchlist_service.get()
    keep = ("name", "category", "price", "change_pct", "from_high_pct", "vs_sma200_pct", "rsi14",
            "notes", "reason", "recommended_by", "analysis")
    items = [{k: getattr(i, k) for k in keep} for i in w.items
             if name is None or name.lower() in i.name.lower()]
    return {"captured_at": str(w.captured_at), "stale": w.stale, "items": items}


def _instagram() -> dict:
    from datetime import datetime

    from app.instagram_content.dashboard import build_dashboard
    from app.telegram_instagram.schedule import _timezone, next_slot, posted_today
    d = build_dashboard(recent_limit=5)
    due = next_slot()
    return {
        "needs_review": d.needs_your_review, "approved_ready": d.approved_ready_to_publish,
        "posted_total": d.posted_total, "post_failed": d.post_failed,
        "pool_available": d.media_pool_available, "drafts_pending": d.curated_drafts_pending,
        "posted_today": posted_today(datetime.now(_timezone()).date()),
        "next_slot": f"{due.hour:02d}:{due.minute:02d} {due.kind}",
        "recent": [{"status": c.status, "caption": (c.caption_draft or "")[:160]} for c in d.recent_candidates],
    }


TOOLS: list[dict] = [
    {"name": "trading_status",
     "description": "Brano's copier accounts right now: balance, equity, open positions, P&L per signal group "
                    "(today, week, total) and whether each copier is online.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "watchlist",
     "description": "The watchlist: price, change today, distance from the 52-week high, against the 200-day "
                    "average, RSI, alert notes, why someone recommended it. Optional name filter.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}}},
    {"name": "instagram_status",
     "description": "Instagram pipeline: posts waiting for review, ready, posted, failed, media pool, the next "
                    "posting slot and the latest captions.",
     "input_schema": {"type": "object", "properties": {}}},
]

_RUN: dict[str, Callable[..., dict]] = {
    "trading_status": lambda **_: _trading(),
    "watchlist": lambda name=None, **_: _watchlist(name),
    "instagram_status": lambda **_: _instagram(),
}


def run(name: str, args: dict) -> tuple[str, bool]:
    """The tool's answer as JSON text, and whether it failed."""
    fn = _RUN.get(name)
    if fn is None:
        return f"unknown tool {name}", True
    try:
        return json.dumps(fn(**(args or {})), default=str, ensure_ascii=False), False
    except Exception as exc:  # noqa: BLE001 -- the model gets the error and says so, instead of the chat dying
        return f"{type(exc).__name__}: {exc}", True
