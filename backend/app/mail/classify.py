"""Which mails matter: Claude reads sender, subject and the first lines, a batch at a time.

Important means something Brano has to know or do -- authorities, tax office,
bank, insurance, contracts, deadlines, bills and reminders, a real person writing
to him. Not important: newsletters, shops, marketing, automatic notifications.
"""
from __future__ import annotations

import json
import os
import re

import httpx

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
CATEGORIES = ("behoerde", "steuer", "bank", "versicherung", "vertrag", "frist", "rechnung", "person",
              "trading", "newsletter", "werbung", "benachrichtigung", "sonstiges")


class ClassifyError(RuntimeError):
    pass


def prompt(mails: list[dict]) -> str:
    rows = "\n".join(f'{i}. id={m["id"]} | Von: {m["from"]} | Betreff: {m["subject"]} | Anfang: {m["snippet"][:300]}'
                     for i, m in enumerate(mails, 1))
    return f"""Du sortierst Brano's Posteingang (er lebt in Deutschland, Bad Kissingen; Trader).
Wichtig (important=true) ist, was er wissen oder tun muss: Behörden, Finanzamt, Jobcenter, Gerichte,
Bank, Versicherung, Verträge, Fristen, Mahnungen, Rechnungen, ein echter Mensch, der ihm persönlich schreibt.
Nicht wichtig: Newsletter, Shops, Werbung, Rabatte, Social Media, automatische Benachrichtigungen
(Logins, Versandstatus, App-Updates), Trading-Signale und Broker-Werbung.

Mails:
{rows}

Antworte NUR mit einem JSON-Array, ein Objekt je Mail, gleiche Reihenfolge:
[{{"id": "...", "important": true|false, "category": eine von {list(CATEGORIES)},
  "summary": "ein kurzer deutscher Satz: worum geht es, was ist zu tun, ggf. Frist"}}]"""


def classify(mails: list[dict], client: httpx.Client | None = None) -> list[dict]:
    if not mails:
        return []
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise ClassifyError("ANTHROPIC_API_KEY is not set")
    c = client or httpx.Client()
    try:
        r = c.post(ANTHROPIC_MESSAGES_URL, timeout=90, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": os.getenv("AURON_MAIL_MODEL") or "claude-haiku-5-5", "max_tokens": 4000,
                  "messages": [{"role": "user", "content": prompt(mails)}]})
    except httpx.HTTPError as exc:
        raise ClassifyError(f"Could not reach the Anthropic API: {exc}") from exc
    if r.status_code >= 400:
        raise ClassifyError(f"Anthropic API returned {r.status_code}: {r.text[:300]}")
    text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise ClassifyError("no JSON in the answer")
    out = {str(x.get("id")): x for x in json.loads(m.group(0)) if isinstance(x, dict)}
    # Anything the model skipped counts as unread-but-unsorted, not as unimportant.
    return [{"id": mm["id"], "important": bool(out.get(mm["id"], {}).get("important", False)),
             "category": str(out.get(mm["id"], {}).get("category", "sonstiges"))[:40],
             "summary": str(out.get(mm["id"], {}).get("summary", ""))[:500],
             "sorted": mm["id"] in out} for mm in mails]
