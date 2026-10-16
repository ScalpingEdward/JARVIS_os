"""AURON on Telegram: Brano writes or speaks to the bot, AURON answers.

The laptop's microphone is broken (2026-10-16), so the phone is the way to talk:
a voice note comes back as text plus a voice note in AURON's voice; a typed
message gets a typed answer. Only Brano's chat (TELEGRAM_CHAT_ID) is answered --
everyone else who finds the bot gets silence, not AURON's view of his accounts.

The conversation is kept in memory, the last turns per chat: an API restart starts
a fresh one, like the "Neu" button on the dashboard.
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict, deque

import httpx

from . import voice
from .brain import AssistantError, reply

log = logging.getLogger(__name__)
KEEP = 20
VOICE = {"provider": "elevenlabs", "voice": "JBFqnCBsd6RMkjVDRZzb", "model": "eleven_v4", "accent": "British accent"}
_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=KEEP))


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/{method}"


def is_for_auron(update: dict) -> bool:
    msg = update.get("message") or {}
    return bool(msg) and (bool(msg.get("text")) or bool(msg.get("voice"))) and not (msg.get("text") or "").startswith("/start")


def handle_message(update: dict, client: httpx.Client | None = None) -> str | None:
    """Answer one message. Returns the answer text (None when the chat is not Brano's)."""
    msg = update.get("message") or {}
    chat = str((msg.get("chat") or {}).get("id", ""))
    allowed = os.getenv("TELEGRAM_CHAT_ID")
    if not allowed or chat != str(allowed):
        log.warning("telegram message from chat %s ignored (not Brano's)", chat)
        return None
    c, close = (client, False) if client else (httpx.Client(), True)
    try:
        spoken = bool(msg.get("voice"))
        c.post(_api("sendChatAction"), json={"chat_id": chat, "action": "record_voice" if spoken else "typing"}, timeout=10)
        try:
            text = _heard(c, msg) if spoken else msg["text"]
        except voice.VoiceError as exc:
            _send(c, chat, f"Verzeihung, Sir, das habe ich akustisch nicht verstanden. ({exc})")
            return None
        if not text:
            _send(c, chat, "Da war nichts zu hören, Sir.")
            return None
        hist = _history[chat]
        hist.append({"role": "user", "content": text})
        try:
            answer = reply(list(hist), "de")["text"]
        except AssistantError as exc:
            hist.pop()
            _send(c, chat, f"Mein Kopf streikt gerade, Sir: {exc}")
            return None
        hist.append({"role": "assistant", "content": answer})
        shown = voice.strip_tags(answer)
        _send(c, chat, f"🎙 {text}\n\n{shown}" if spoken else shown)
        if spoken:
            try:
                audio = voice.speak(answer, VOICE["provider"], VOICE["voice"], VOICE["model"], VOICE["accent"], client=c, fmt="ogg")
                c.post(_api("sendVoice"), data={"chat_id": chat}, files={"voice": ("auron.ogg", audio, "audio/ogg")}, timeout=60)
            except (voice.VoiceError, httpx.HTTPError) as exc:
                log.warning("voice reply failed: %s", exc)   # the text is already there
        return answer
    finally:
        if close:
            c.close()


def _heard(c: httpx.Client, msg: dict) -> str:
    try:
        info = c.post(_api("getFile"), json={"file_id": msg["voice"]["file_id"]}, timeout=20).json()
        path = info["result"]["file_path"]
        audio = c.get(f"https://api.telegram.org/file/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/{path}", timeout=60).content
    except (httpx.HTTPError, KeyError) as exc:
        raise voice.VoiceError(f"could not fetch the voice note: {exc}") from exc
    return voice.transcribe(audio, msg["voice"].get("mime_type") or "audio/ogg", "de", client=c)


def _send(c: httpx.Client, chat: str, text: str) -> None:
    c.post(_api("sendMessage"), json={"chat_id": chat, "text": text[:4000]}, timeout=20)
