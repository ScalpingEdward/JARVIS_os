"""AURON's voice: text in, MP3 out -- ElevenLabs, or OpenAI as the alternative.

ElevenLabs v3/v4 understand audio tags ([laughs], [sighs], ...): the chat prompt lets
AURON use one now and then, the dashboard hides them in the text, and here they are
kept for those models and stripped for the others, which would read them out.
The key only needs "Text to Speech"; the voices are ElevenLabs' standard ones, listed
here, so it needs no right to read the account's voice list.
"""
from __future__ import annotations

import os
import re
from collections import OrderedDict

import httpx

ELEVEN_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format={fmt}"
FORMATS = {"mp3": "mp3_44100_128", "ogg": "opus_48000_64"}  # ogg/opus: what Telegram plays as a voice note
OPENAI_URL = "https://api.openai.com/v1/audio/speech"
MAX_CHARS = 2500

# ElevenLabs' standard voices (the same IDs for every account).
ELEVEN_VOICES = [
    ("onwK4e9ZLuTAKqWW03F9", "Daniel", "britisch, tief, ruhig – Nachrichtensprecher"),
    ("JBFqnCBsd6RMkjVDRZzb", "George", "britisch, warm, erzählend"),
    ("nPczCjzI2devNBz1zQrb", "Brian", "tief, sonor, amerikanisch"),
    ("pNInz6obpgDQGcFmaJgB", "Adam", "tief, kräftig, amerikanisch"),
    ("N2lVS1w4EtoT3dr4eOWO", "Callum", "rau, intensiv"),
    ("cjVigY5qzO86Huf0OWal", "Eric", "weich, vertrauensvoll"),
    ("iP95p4xoKVk53GoZ742B", "Chris", "locker, natürlich"),
    ("TX3LPaxmHKxFdv7VOQHJ", "Liam", "jung, energisch"),
    ("EXAVITQu4vr4xnSDxMaL", "Sarah", "weiblich, weich, sicher"),
    ("XrExE9yKIg1WjnnlVkGX", "Matilda", "weiblich, freundlich, warm"),
]
ELEVEN_MODELS = {"eleven_v4": "v4 – neu, ausdrucksstark", "eleven_v3": "v3 – ausdrucksstark",
                 "eleven_multilingual_v2": "v2 – ruhig, stabil", "eleven_flash_v2_5": "Flash – am schnellsten"}
TAG_MODELS = {"eleven_v3", "eleven_v4"}
OPENAI_VOICES = ["onyx", "ash", "echo", "ballad", "verse", "sage", "coral", "nova"]
OPENAI_INSTRUCTIONS = ("Sprich wie ein vertrauter, warmer Assistent mit trockenem Humor: natürlich, entspannt, "
                       "nicht wie ein Ansager. Lachen, wo der Text lacht.")

TAG = re.compile(r"\[[a-zA-Z ]{2,24}\]\s*")
_cache: OrderedDict[tuple, bytes] = OrderedDict()  # the comparison plays the same lines again and again


class VoiceError(RuntimeError):
    pass


def strip_tags(text: str) -> str:
    return TAG.sub("", text).strip()


def voices() -> dict:
    return {
        "elevenlabs": {"available": bool(os.getenv("ELEVENLABS_API_KEY")),
                       "voices": [{"id": i, "name": n, "desc": d} for i, n, d in ELEVEN_VOICES],
                       "models": [{"id": k, "name": v} for k, v in ELEVEN_MODELS.items()]},
        "openai": {"available": bool(os.getenv("OPENAI_API_KEY")),
                   "voices": [{"id": v, "name": v.capitalize(), "desc": ""} for v in OPENAI_VOICES],
                   "models": [{"id": "gpt-4o-mini-tts", "name": "gpt-4o-mini-tts"}]},
    }


def speak(text: str, provider: str, voice: str, model: str, accent: str = "",
          client: httpx.Client | None = None, fmt: str = "mp3") -> bytes:
    """accent: e.g. "British accent" -- put in front as a tag, so v3/v4 speak German the way the voice is from."""
    text = text.strip()[:MAX_CHARS]
    if provider == "openai" or model not in TAG_MODELS:
        text = strip_tags(text)
    elif accent:
        text = f"[{accent}] {text}"
    if not text:
        raise VoiceError("nothing to say")
    key = (text, provider, voice, model, fmt)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    c, close = (client, False) if client else (httpx.Client(), True)
    try:
        if provider == "elevenlabs":
            api_key = os.getenv("ELEVENLABS_API_KEY")
            if not api_key:
                raise VoiceError("ELEVENLABS_API_KEY is not set")
            r = c.post(ELEVEN_URL.format(voice=voice, fmt=FORMATS[fmt]), timeout=60, headers={"xi-api-key": api_key},
                       json={"text": text, "model_id": model})
        elif provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise VoiceError("OPENAI_API_KEY is not set")
            r = c.post(OPENAI_URL, timeout=60, headers={"Authorization": f"Bearer {api_key}"},
                       json={"model": model, "voice": voice, "input": text, "instructions": OPENAI_INSTRUCTIONS,
                             "response_format": "opus" if fmt == "ogg" else "mp3"})
        else:
            raise VoiceError(f"unknown provider {provider}")
        if r.status_code >= 400:
            raise VoiceError(f"{provider} returned {r.status_code}: {r.text[:300]}")
    except httpx.HTTPError as exc:
        raise VoiceError(f"Could not reach {provider}: {exc}") from exc
    finally:
        if close:
            c.close()
    _cache[key] = r.content
    while len(_cache) > 60:
        _cache.popitem(last=False)
    return r.content


STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
STT_LANG = {"de": "de", "en": "en", "sk": "sk"}
MAX_AUDIO = 10 * 1024 * 1024  # about ten minutes of browser webm/opus


def transcribe(audio: bytes, content_type: str, lang: str = "de", client: httpx.Client | None = None) -> str:
    """What Brano said, as text (ElevenLabs Scribe)."""
    if not audio:
        raise VoiceError("no audio")
    if len(audio) > MAX_AUDIO:
        raise VoiceError("recording too long")
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise VoiceError("ELEVENLABS_API_KEY is not set")
    ext = "webm" if "webm" in content_type else "ogg" if "ogg" in content_type else "mp4" if "mp4" in content_type else "mp3"
    c, close = (client, False) if client else (httpx.Client(), True)
    try:
        r = c.post(STT_URL, timeout=60, headers={"xi-api-key": api_key},
                   data={"model_id": "scribe_v2", "language_code": STT_LANG.get(lang, "de"), "tag_audio_events": "false"},
                   files={"file": (f"speech.{ext}", audio, content_type or "application/octet-stream")})
        if r.status_code >= 400:
            raise VoiceError(f"elevenlabs returned {r.status_code}: {r.text[:300]}")
        return (r.json().get("text") or "").strip()
    except httpx.HTTPError as exc:
        raise VoiceError(f"Could not reach elevenlabs: {exc}") from exc
    finally:
        if close:
            c.close()
