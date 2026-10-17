"""The week's market-moving dates: CPI, jobs report, central banks -- the high-impact ones.

Source: the weekly calendar feed Forex Factory publishes as JSON (nfs.faireconomy.media).
It asks to be fetched sparingly, so it is fetched at most once an hour and kept in memory.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx

FEED = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
REFRESH_S = 3600
# Currencies that move what Brano trades and watches: gold and US indices first.
CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CNY", "CHF"}
NAMES_DE = {  # the usual suspects, in words he reads at a glance
    "CPI": "Inflation", "Core CPI": "Kerninflation", "Non-Farm Employment Change": "US-Arbeitsmarkt (NFP)",
    "Unemployment Rate": "Arbeitslosenquote", "Federal Funds Rate": "Fed-Zinsentscheid", "FOMC": "Fed",
    "Retail Sales": "Einzelhandel", "GDP": "BIP", "PPI": "Erzeugerpreise", "Main Refinancing Rate": "EZB-Zinsentscheid",
    "Bank Rate": "BoE-Zinsentscheid", "Powell Speaks": "Powell spricht", "Lagarde Speaks": "Lagarde spricht",
}


class MacroError(RuntimeError):
    pass


_cache: tuple[float, list[dict]] = (0.0, [])


def _german(title: str) -> str:
    for en, de in NAMES_DE.items():
        if en.lower() in title.lower():
            return de
    return ""


def events(client: httpx.Client | None = None, now: float | None = None) -> list[dict]:
    """This week's high-impact events for the currencies above, oldest first."""
    global _cache
    now = now or time.time()
    if _cache[1] and now - _cache[0] < REFRESH_S:
        return _cache[1]
    c = client or httpx.Client(timeout=20)
    try:
        r = c.get(FEED, headers={"User-Agent": "AURON dashboard (personal, hourly)"})
    except httpx.HTTPError as exc:
        if _cache[1]:
            return _cache[1]
        raise MacroError(f"calendar unreachable: {exc}") from exc
    if r.status_code >= 400:
        if _cache[1]:
            return _cache[1]  # the feed refuses now and then; last hour's list is still right
        raise MacroError(f"calendar returned {r.status_code}")
    out = []
    for e in r.json():
        if e.get("impact") != "High" or e.get("country") not in CURRENCIES:
            continue
        try:
            at = datetime.fromisoformat(e["date"]).astimezone(timezone.utc)
        except (KeyError, ValueError):
            continue
        out.append({"title": e.get("title", ""), "title_de": _german(e.get("title", "")), "currency": e["country"],
                    "at": at.isoformat(), "forecast": e.get("forecast", ""), "previous": e.get("previous", "")})
    out.sort(key=lambda x: x["at"])
    _cache = (now, out)
    return out


def upcoming(evts: list[dict], now: datetime | None = None, hours: float = 24 * 7) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    return [e for e in evts if 0 <= (datetime.fromisoformat(e["at"]) - now).total_seconds() <= hours * 3600]


def due_for_alert(evts: list[dict], now: datetime | None = None, lead_min: float = 30) -> list[dict]:
    """Events starting in the next lead_min minutes (a minute's slack either side)."""
    now = now or datetime.now(timezone.utc)
    return [e for e in evts if -60 <= (datetime.fromisoformat(e["at"]) - now).total_seconds() <= lead_min * 60]
