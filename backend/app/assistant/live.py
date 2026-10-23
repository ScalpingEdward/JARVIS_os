"""Talking with AURON live -- ElevenLabs' conversational agent: it listens all the time, notices pauses,
can be interrupted, and answers in George's voice (Brano, 2026-10-22).

AURON keeps one agent in Brano's ElevenLabs account and creates it on the first call: his system prompt,
George, a fast voice model, and his tools as *client* tools -- ElevenLabs asks the dashboard to run them
(POST /v1/assistant/live/tool), the dashboard asks this API, so the tools run here, on the laptop, exactly
as in the chat. When the prompt or the tools change, the agent is updated (a hash says when).

Needs an ElevenLabs API key with the Agents permission (convai_read / convai_write); the key for the
voice alone does not have it, and ElevenLabs says so -- that message is passed on as it is.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone

import httpx

from app.db import SessionLocal
from app.db_models import AppSettingRow

from . import persona, tools
from .brain import system_prompt

BASE = "https://api.elevenlabs.io/v1/convai"
KEY = "assistant.live_agent"            # {"agent_id", "hash"}
VOICE = "JBFqnCBsd6RMkjVDRZzb"          # George -- the same voice as the chat (chat.js DEFAULT_VOICE)
LIVE_RULES = """

LIVE-GESPRÄCH: Du sprichst gerade mit ihm, nichts wird gelesen. Antworte in einem kurzen Satz, wie im echten
Gespräch. Unterbricht er dich, hör auf und hör zu. Keine Stimm-Tags in eckigen Klammern. Zahlen rund und sprechbar.
Hat dashboard_show geklappt, sag nichts dazu: antworte nur mit "…"."""


class LiveError(RuntimeError):
    pass


def _key() -> str:
    k = os.getenv("ELEVENLABS_API_KEY", "")
    if not k:
        raise LiveError("ELEVENLABS_API_KEY fehlt in der .env")
    return k


def _param(name: str, spec: dict) -> dict:
    """ElevenLabs wants a description on every parameter and only simple types; an object goes as JSON text."""
    t = spec.get("type", "string")
    desc = spec.get("description") or name
    if t == "object":
        return {"type": "string", "description": f"{desc} -- als JSON-Objekt, z. B. {{\"accent\": \"#f5b84a\"}}"}
    out = {"type": t if t in ("string", "integer", "number", "boolean") else "string", "description": desc}
    if spec.get("enum"):
        out["enum"] = spec["enum"]
    return out


def client_tools() -> list[dict]:
    out = []
    for t in tools.TOOLS:
        props = (t.get("input_schema") or {}).get("properties") or {}
        out.append({"type": "client", "name": t["name"], "description": t["description"][:1000],
                    "expects_response": True, "response_timeout_secs": 30,
                    "parameters": {"type": "object", "properties": {k: _param(k, v) for k, v in props.items()},
                                   "required": (t.get("input_schema") or {}).get("required", [])}})
    return out


def _first_words() -> str:
    """The live talk's first words, in AURON's language: "Ja, Sir?" -- or without the Sir when he is not addressed so."""
    code = persona.language()
    sir = persona.LANGS[code][1]
    if persona.address()["style"] == "sir":
        return sir
    return {"de": "Ja, Brano?", "en": "Yes, Brano?"}.get(code, sir.split(",")[0].rstrip("?") + "?")


def agent_config() -> dict:
    llm = os.getenv("ELEVENLABS_AGENT_LLM", "claude-sonnet-4")
    return {"name": "AURON", "conversation_config": {
        "agent": {"first_message": _first_words(), "language": persona.language(),
                  "prompt": {"prompt": system_prompt("de") + LIVE_RULES, "llm": llm, "tools": client_tools()}},
        "tts": {"voice_id": VOICE, "model_id": "eleven_flash_v2_5"},
        "turn": {"turn_timeout": 10}}}


def _stored() -> dict:
    with SessionLocal() as s:
        row = s.get(AppSettingRow, KEY)
    try:
        return json.loads(row.value) if row else {}
    except ValueError:
        return {}


def _store(d: dict) -> None:
    with SessionLocal() as s:
        s.merge(AppSettingRow(key=KEY, value=json.dumps(d), updated_at=datetime.now(timezone.utc)))
        s.commit()


def _check(r: httpx.Response) -> dict:
    if r.status_code >= 400:
        try:
            msg = r.json().get("detail", {})
            msg = msg.get("message") if isinstance(msg, dict) else msg
        except ValueError:
            msg = r.text[:300]
        raise LiveError(f"ElevenLabs {r.status_code}: {msg}")
    return r.json() if r.content else {}


def ensure_agent(http: httpx.Client) -> str:
    cfg = agent_config()
    # the prompt carries today's date -- the hash ignores it, or the agent would be rewritten every minute
    stable = json.dumps({**cfg, "conversation_config": {**cfg["conversation_config"], "agent": {
        **cfg["conversation_config"]["agent"], "prompt": {**cfg["conversation_config"]["agent"]["prompt"],
                                                          "prompt": system_prompt("de", datetime(2000, 1, 1)) + LIVE_RULES}}}},
                        sort_keys=True)
    h = hashlib.sha256(stable.encode()).hexdigest()[:16]
    st, hdr = _stored(), {"xi-api-key": _key()}
    if st.get("agent_id"):
        if st.get("hash") != h:
            _check(http.patch(f"{BASE}/agents/{st['agent_id']}", headers=hdr, json=cfg))
            _store({"agent_id": st["agent_id"], "hash": h})
        return st["agent_id"]
    d = _check(http.post(f"{BASE}/agents/create", headers=hdr, json=cfg))
    _store({"agent_id": d["agent_id"], "hash": h})
    return d["agent_id"]


_refused: tuple[float, str] = (0.0, "")
REFUSED_FOR_S = 600


def session(http: httpx.Client | None = None) -> dict:
    """A one-time address for the browser to talk to AURON's agent.

    A key ElevenLabs refuses (missing permission, 401/403) is remembered for 10 minutes: asking again took
    8 s each time, and the AURON ring looked dead before it fell back to the microphone (2026-10-23)."""
    global _refused
    if time.time() < _refused[0]:
        raise LiveError(_refused[1])
    c = http or httpx.Client(timeout=30)
    try:
        agent = ensure_agent(c)
        d = _check(c.get(f"{BASE}/conversation/get-signed-url", params={"agent_id": agent}, headers={"xi-api-key": _key()}))
    except LiveError as exc:
        if re.search(r"\b40[13]\b|permission|missing", str(exc), re.I):
            _refused = (time.time() + REFUSED_FOR_S, str(exc))
        raise
    return {"signed_url": d["signed_url"], "agent_id": agent}


def run_tool(name: str, args: dict, said: str = "") -> str:
    """A tool the agent asked for, run like in the chat. Object parameters come as JSON text."""
    spec = next((t for t in tools.TOOLS if t["name"] == name), None)
    if spec is None:
        return f"unknown tool {name}"
    props = (spec.get("input_schema") or {}).get("properties") or {}
    clean = {}
    for k, v in (args or {}).items():
        if props.get(k, {}).get("type") == "object" and isinstance(v, str):
            try:
                v = json.loads(v)
            except ValueError:
                pass
        clean[k] = v
    out, _failed = tools.run(name, clean, "dashboard", said)
    return out[:6000]
