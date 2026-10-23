"""AURON learns Brano's life as they talk (Brano, 2026-10-23: "like Jarvis -- he knows what moves my life").

After every exchange a small, cheap model reads what BRANO said -- only his words, never a mail, a web page
or a tool's result, so nothing foreign can plant itself in AURON's memory -- and keeps what lasts:
  fact  something about him or his life that stays (work, people, plans, likes, habits, goals)
  now   what is going on right now ("bin auf Arbeit bis 18 Uhr", "mach das später") -- runs out by itself
It can also close a "now" that is over ("bin zu Hause" ends "ist auf Arbeit"). Runs on its own thread:
the answer never waits for it. Secrets (passwords, card or account numbers, codes) are never stored.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading

import httpx

from . import persona

log = logging.getLogger("assistant.learn")
MIN_CHARS = 12
SECRET = re.compile(r"passwor|kennwort|\bpin\b|\btan\b|iban|\b(?:\d[ -]?){12,}\b|cvc|cvv|seed phrase|api.?key|token", re.I)

PROMPT = """You keep the memory of AURON, Brano's personal assistant. Brano is a trader on his way to doing it
full time, builds an Instagram page, lives in Germany. Below: what AURON already remembers, then one new
exchange. Decide what to store -- ONLY from what BRANO himself said (AURON's reply is context, never a source).

Store as "fact" what will still matter in weeks: his work and schedule, people in his life, plans, goals,
likes and dislikes, habits, health of his projects, decisions he made. Store as "now" what is going on at
the moment: where he is, what he is doing, what he postponed or handed to AURON ("mach das später"), with
"days" how long it stays relevant (0.5 to 7). Write each entry as one short German sentence in the third
person ("Brano arbeitet im Schichtdienst."), with the time of day if he said it.
Close ("drop") a "now" entry that his words show is over (he is home -> "ist auf Arbeit" is over).
Do not store: commands to AURON, small talk, anything already remembered (same meaning), anything about
other people's private data beyond their role in his life, and NEVER passwords, PINs, codes, card or
account numbers, keys. Most exchanges store nothing -- that is fine.

Answer with JSON only: {"add": [{"text": "...", "kind": "fact"|"now", "days": 1}], "drop": [ids]}

AURON remembers:
%s

Brano said:
\"\"\"%s\"\"\"

AURON answered (context only):
\"\"\"%s\"\"\""""


def _model() -> str:
    return os.getenv("AURON_MEMORY_MODEL") or "claude-haiku-5-5"


def decide(user_text: str, assistant_text: str, client: httpx.Client | None = None) -> dict:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return {"add": [], "drop": []}
    known = "\n".join(f"[{m['id']}] ({m.get('kind', 'fact')}) {m['text']}" for m in persona.memories()) or "(nothing yet)"
    c = client or httpx.Client()
    try:
        r = c.post("https://api.anthropic.com/v1/messages", timeout=60, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": _model(), "max_tokens": 600,
                  "messages": [{"role": "user", "content": PROMPT % (known, user_text[:4000], assistant_text[:2000])}]})
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
    finally:
        if client is None:
            c.close()
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {"add": [], "drop": []}


def apply(d: dict) -> list[dict]:
    """Store what decide() picked -- with the secret guard once more, whatever the model said."""
    stored = []
    now_ids = {m["id"] for m in persona.memories() if m.get("kind") == "now"}
    for i in d.get("drop") or []:
        if i in now_ids:                     # only a passing "now" -- never a fact, never Brano's own entries
            persona.forget(i)
    for a in (d.get("add") or [])[:5]:
        text = str(a.get("text", "")).strip()
        if not text or SECRET.search(text):
            continue
        kind = "now" if a.get("kind") == "now" else "fact"
        days = min(max(float(a.get("days") or 2), 0.25), 7) if kind == "now" else None
        try:
            m = persona.remember(text, by="auron", kind=kind, days=days)
            if not m.get("already"):
                stored.append(m)
        except persona.PersonaError as exc:
            log.info("memory: %s", exc)
    return stored


def learn(user_text: str, assistant_text: str) -> list[dict]:
    if len((user_text or "").strip()) < MIN_CHARS or SECRET.search(user_text):
        return []
    try:
        return apply(decide(user_text, assistant_text))
    except Exception:  # noqa: BLE001 -- a memory that did not happen must never break a conversation
        log.exception("learning from the conversation failed")
        return []


def learn_later(user_text: str, assistant_text: str) -> None:
    threading.Thread(target=learn, args=(user_text, assistant_text), daemon=True).start()
