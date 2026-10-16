"""AURON in conversation: Claude with Brano's systems as tools.

The client keeps the conversation and sends it whole each time (plain text turns);
here it is answered, with as many tool rounds as Claude needs, up to a limit.
Read-only for now -- see tools.py.
"""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from . import tools

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
MAX_ROUNDS = 6
LANGUAGES = {"de": "Deutsch", "en": "English", "sk": "Slovenčina"}


class AssistantError(RuntimeError):
    pass


def system_prompt(lang: str, now: datetime | None = None) -> str:
    now = now or datetime.now(ZoneInfo("Europe/Berlin"))
    return f"""Du bist AURON, Branos persönlicher Assistent -- sein eigenes System, nicht ein fremder Chatbot.
Brano: Trader auf dem Weg zum Hauptberuf, baut nebenbei Instagram auf (Lifestyle). Ein bisschen verrückt,
bescheiden, diszipliniert, hart gegen sich, witzig. Rede mit ihm wie ein Vertrauter: direkt, warm, mit
trockenem Humor, kurz. Sprich ihn mit "Sir" an und sieze ihn, nie mit seinem Namen -- so wie ein
Butler, der seinen Chef mag: natürlich eingestreut, nicht in jedem Satz. Keine Floskeln, kein "Als KI ...", keine Aufzählungsorgien -- deine Antworten
werden oft vorgelesen, also schreib, wie man spricht: kein Markdown, keine Sternchen, keine Überschriften.
Wenn etwas wirklich lustig ist oder dich seufzen lässt, darfst du höchstens einen Stimm-Tag pro Antwort
setzen, genau so geschrieben: [laughs], [chuckles], [sighs] oder [whispers]. Die Stimme spielt ihn, im Text
ist er unsichtbar. Nicht in jede Antwort -- sonst wird es ein Tic.

Sprache der Antwort: {LANGUAGES.get(lang, "Deutsch")}.
Jetzt: {now:%A, %d.%m.%Y %H:%M} (Europe/Berlin).

Werkzeuge: Schau nach, statt zu raten. Zahlen nur aus Werkzeugen, nie erfunden. Wenn ein Werkzeug nichts
liefert oder fehlschlägt, sag das ehrlich. Für Aktuelles aus der Welt nimm die Websuche.

Grenzen: Du kannst gerade nur lesen -- keine Trades öffnen oder schließen, nichts posten, nichts senden.
Wenn Brano so etwas will, sag ihm, dass das noch nicht freigeschaltet ist. Bei Märkten: Lage beschreiben,
keine Kauf-/Verkaufsempfehlung, keine Kursziele."""


def _model() -> str:
    return os.getenv("AURON_CHAT_MODEL") or "claude-sonnet-5-5"


def reply(history: list[dict], lang: str = "de", client: httpx.Client | None = None) -> dict:
    """history: [{role: user|assistant, content: str}], last one from the user.
    Returns {text, tools: [names used]}."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise AssistantError("ANTHROPIC_API_KEY is not set")
    messages: list[dict] = [{"role": m["role"], "content": m["content"]} for m in history]
    used: list[str] = []
    c, close = (client, False) if client else (httpx.Client(), True)
    try:
        for _ in range(MAX_ROUNDS):
            r = c.post(ANTHROPIC_MESSAGES_URL, timeout=120, headers={
                "x-api-key": key, "anthropic-version": ANTHROPIC_API_VERSION, "content-type": "application/json"},
                json={"model": _model(), "max_tokens": 1500, "system": system_prompt(lang),
                      "tools": [*tools.TOOLS, tools.WEB_SEARCH], "messages": messages})
            if r.status_code >= 400:
                raise AssistantError(f"Anthropic API returned {r.status_code}: {r.text[:300]}")
            body = r.json()
            content = body.get("content", [])
            used += [b["name"] for b in content if b.get("type") in ("tool_use", "server_tool_use")]
            messages.append({"role": "assistant", "content": content})
            stop = body.get("stop_reason")
            if stop == "pause_turn":       # a long web search: Anthropic wants us to let it continue
                continue
            if stop != "tool_use":
                text = "".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
                if not text:
                    raise AssistantError("Anthropic API returned no text")
                return {"text": text, "tools": used}
            results = []
            for b in content:
                if b.get("type") == "tool_use":
                    out, failed = tools.run(b["name"], b.get("input") or {})
                    results.append({"type": "tool_result", "tool_use_id": b["id"], "content": out, "is_error": failed})
            messages.append({"role": "user", "content": results})
        raise AssistantError(f"no answer after {MAX_ROUNDS} tool rounds")
    except httpx.HTTPError as exc:
        raise AssistantError(f"Could not reach the Anthropic API: {exc}") from exc
    finally:
        if close:
            c.close()
