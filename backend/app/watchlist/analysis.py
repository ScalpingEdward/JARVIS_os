"""AURON's short read on one watchlist symbol, written by Claude.

In: the symbol's facts (price against its 52-week range, 200-day average, RSI), the reason
whoever recommended it gave, and -- when a Tavily key is set -- a handful of current
headlines. Out: a few plain German lines on what speaks for and against it right now.
Deliberately not advice: no buy/sell call, no price target; the prompt says so and the
dashboard says so.
"""
from __future__ import annotations

import os

import httpx

from .models import WatchItem

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


class AnalysisError(RuntimeError):
    pass


def _facts(item: WatchItem) -> str:
    parts = []
    if item.price is not None:
        parts.append(f"Kurs {item.price}")
    for label, v in (("heute", item.change_pct), ("vom 52-Wochen-Hoch", item.from_high_pct),
                     ("gegenüber 200-Tage-Schnitt", item.vs_sma200_pct)):
        if v is not None:
            parts.append(f"{label} {v:+.1f} %")
    if item.rsi14 is not None:
        parts.append(f"RSI {item.rsi14:.0f}")
    return ", ".join(parts) or "keine Kursdaten"


def _headlines(name: str) -> str:
    if not os.getenv("TAVILY_API_KEY"):
        return ""
    try:
        from app.instagram_content.web_research import TavilyWebResearcher
        res = TavilyWebResearcher().search(f"{name} stock news", max_results=5)
        return "\n".join(f"- {r.title}: {r.content[:200]}" for r in res.results)
    except Exception:  # noqa: BLE001 -- news are a bonus; the read works without them
        return ""


def build_prompt(item: WatchItem, reason: str, recommended_by: str, headlines: str) -> str:
    who = f" (empfohlen von {recommended_by})" if recommended_by else ""
    return f"""Du bist AURON, der Assistent von Brano. Er beobachtet {item.name} ({item.category}){who}.

Begründung der Empfehlung: {reason or "keine angegeben"}
Kennzahlen jetzt: {_facts(item)}
{("Aktuelle Schlagzeilen:\n" + headlines) if headlines else "Keine aktuellen Nachrichten verfügbar."}

Schreib auf Deutsch, knapp, höchstens 120 Wörter, mit diesen vier Zeilen:
Was es ist: …
Dafür spricht: …
Dagegen spricht / Risiken: …
Was die Kennzahlen sagen: … (z. B. weit unter dem Hoch, unter dem 200-Tage-Schnitt, RSI)

Wichtig: keine Kauf- oder Verkaufsempfehlung, keine Kursziele, keine Zeitpunkt-Empfehlung.
Beschreibe nur, was die Lage ist. Erfinde keine Zahlen oder Nachrichten, die oben nicht stehen."""


def analyse(item: WatchItem, reason: str, recommended_by: str, client: httpx.Client | None = None) -> str:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise AnalysisError("ANTHROPIC_API_KEY is not set")
    prompt = build_prompt(item, reason, recommended_by, _headlines(item.name))
    c, close = (client, False) if client else (httpx.Client(), True)
    try:
        r = c.post(ANTHROPIC_MESSAGES_URL, timeout=60, headers={
            "x-api-key": key, "anthropic-version": ANTHROPIC_API_VERSION, "content-type": "application/json"},
            json={"model": os.getenv("AURON_ANALYSIS_MODEL") or os.getenv("AURON_CAPTION_MODEL") or "claude-sonnet-5",
                  "max_tokens": 600, "messages": [{"role": "user", "content": prompt}]})
        if r.status_code >= 400:
            raise AnalysisError(f"Anthropic API returned {r.status_code}: {r.text[:300]}")
        text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text").strip()
        if not text:
            raise AnalysisError("Anthropic API returned no text")
        return text
    except httpx.HTTPError as exc:
        raise AnalysisError(f"Could not reach the Anthropic API: {exc}") from exc
    finally:
        if close:
            c.close()
