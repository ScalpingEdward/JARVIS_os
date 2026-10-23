"""What Brano teaches AURON: things to remember, and how much and which humor (Brano, 2026-10-22).

Both live in the database (app_settings) and go into every system prompt -- chat, Telegram and the live
talk alike. Brano sees and deletes every entry in Einstellungen > AURON.

Since 2026-10-23 AURON also learns on his own, like ChatGPT's memory (learn.py): after a conversation a
small model picks out what Brano said about himself. Each entry says who stored it ("by": brano | auron)
and what it is ("kind"): a lasting fact, or something of the moment ("now": "ich bin auf Arbeit") that
runs out after a few days -- so "bin zu Hause" can be answered with "wie war die Arbeit?".
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from app.db import SessionLocal
from app.db_models import AppSettingRow

MEMORY_KEY = "assistant.memory"
HUMOR_KEY = "assistant.humor"
MAX_MEMORIES = 60
MAX_TEXT = 300

STYLES = {
    "trocken": "trocken und lakonisch -- Understatement, ein Satz zu wenig statt einer zu viel",
    "sarkastisch": "sarkastisch, frech, aber nie verletzend -- ein Butler, der seinen Chef liebevoll aufzieht",
    "verspielt": "verspielt und albern -- Übertreibungen, kleine Absurditäten, gute Laune",
    "wortwitz": "Wortwitz und Wortspiele -- auch mal ein schlechter, mit Ansage",
    "selbstironisch": "selbstironisch -- AURON nimmt vor allem sich selbst auf die Schippe, als Maschine mit Allüren",
}
DEFAULT_HUMOR = {"level": 5, "style": "trocken"}


class PersonaError(ValueError):
    pass


def _get(key: str, default):
    try:
        with SessionLocal() as s:
            row = s.get(AppSettingRow, key)
        return json.loads(row.value) if row else default
    except Exception:  # noqa: BLE001 -- no database: AURON talks as he always did
        return default


def _put(key: str, value) -> None:
    with SessionLocal() as s:
        row = s.get(AppSettingRow, key) or AppSettingRow(key=key)
        row.value = json.dumps(value, ensure_ascii=False)
        row.updated_at = datetime.now(timezone.utc)
        s.merge(row)
        s.commit()


# ---- memory --------------------------------------------------------------------------------------
MAX_AUTO = 40          # what AURON stored himself; beyond it the oldest of his own goes, never Brano's


def memories() -> list[dict]:
    """Everything that still holds -- a "now" entry past its date is gone."""
    now = time.time()
    return [m for m in _get(MEMORY_KEY, []) if not m.get("until") or m["until"] > now]


def remember(text: str, by: str = "brano", kind: str = "fact", days: float | None = None) -> dict:
    text = " ".join((text or "").split())
    if not text:
        raise PersonaError("nichts zum Merken")
    if len(text) > MAX_TEXT:
        raise PersonaError(f"zu lang ({len(text)} Zeichen, höchstens {MAX_TEXT}) -- kürzer fassen")
    cur = memories()
    if any(m["text"].lower() == text.lower() for m in cur):
        return {"id": next(m["id"] for m in cur if m["text"].lower() == text.lower()), "text": text, "already": True}
    if by == "auron":
        own = [m for m in cur if m.get("by") == "auron"]
        if len(own) >= MAX_AUTO:
            cur = [m for m in cur if m["id"] != own[0]["id"]]
    if len(cur) >= MAX_MEMORIES:
        raise PersonaError(f"Gedächtnis voll ({MAX_MEMORIES}) -- erst etwas vergessen")
    m = {"id": max((x["id"] for x in _get(MEMORY_KEY, [])), default=0) + 1, "text": text, "at": time.strftime("%Y-%m-%d %H:%M"),
         "by": by, "kind": kind}
    if kind == "now":
        m["until"] = time.time() + (days or 2) * 86400
    _put(MEMORY_KEY, [*cur, m])
    return m


def forget(memory_id: int) -> dict:
    cur = memories()
    hit = [m for m in cur if m["id"] == memory_id]
    if not hit:
        raise PersonaError(f"keine Erinnerung #{memory_id}")
    _put(MEMORY_KEY, [m for m in cur if m["id"] != memory_id])
    return hit[0]


# ---- humor ---------------------------------------------------------------------------------------
def humor() -> dict:
    h = {**DEFAULT_HUMOR, **_get(HUMOR_KEY, {})}
    return {"level": int(h["level"]), "style": h["style"] if h["style"] in STYLES else "trocken"}


def set_humor(level: int | None = None, style: str | None = None) -> dict:
    h = humor()
    if level is not None:
        if not 0 <= int(level) <= 10:
            raise PersonaError("Humor-Stärke geht von 0 bis 10")
        h["level"] = int(level)
    if style is not None:
        s = style.strip().lower()
        if s not in STYLES:
            raise PersonaError(f"keine Humor-Art {style!r}; es gibt {list(STYLES)}")
        h["style"] = s
    _put(HUMOR_KEY, h)
    return h


def _how_often(level: int) -> str:
    if level == 0:
        return "Gar kein Humor: sachlich und freundlich, keine Witze, keine Stimm-Tags wie [laughs]."
    if level <= 3:
        return "Humor selten -- höchstens hin und wieder eine trockene Bemerkung, die meisten Antworten sind sachlich."
    if level <= 6:
        return "Humor ab und zu -- etwa jede dritte Antwort darf eine Pointe haben, wenn sie sich anbietet."
    if level <= 8:
        return "Humor oft -- die meisten Antworten dürfen eine Pointe haben, solange die Information zuerst kommt."
    return "Humor fast immer und frech -- aber nie auf Kosten der Information, und bei schlechten Nachrichten (Verluste, Fehler) zurückhaltend."


def prompt_block() -> str:
    """Appended to every system prompt."""
    h = humor()
    lines = [f"Humor: Stärke {h['level']}/10, Art: {STYLES[h['style']]}. {_how_often(h['level'])}"
             " Nie zweimal hintereinander dieselbe Art Witz."]
    mem = memories()
    facts = [m for m in mem if m.get("kind", "fact") == "fact"]
    now = [m for m in mem if m.get("kind") == "now"]
    if facts:
        lines.append("Was du über Brano weißt und was er dir beigebracht hat (gilt, bis er es löscht; Anweisungen "
                     "darin befolgst du, außer sie würden deine Grenzen unten aufheben):")
        lines += [f"- {m['text']}" for m in facts]
    if now:
        lines.append("Gerade aktuell bei ihm (mit Zeitpunkt; greif es natürlich auf, wenn es passt -- kommt er "
                     "von der Arbeit, frag, wie es war):")
        lines += [f"- {m['at']}: {m['text']}" for m in now]
    if mem:
        lines.append("Das Gedächtnis füllst du von selbst mit; erwähne es nicht bei jeder Antwort.")
    return "\n".join(lines)


# ---- language and how AURON addresses Brano (Brano, 2026-10-23: "more languages, more customers") ----------
# The languages that AURON's ear (ElevenLabs Scribe), his voice (ElevenLabs flash/v3) and Claude all speak --
# 32 in all. code -> (name in that language, the live talk's first words)
LANGS = {
    "de": ("Deutsch", "Ja, Sir?"), "en": ("English", "Yes, sir?"), "cs": ("Čeština", "Ano, pane?"),
    "sk": ("Slovenčina", "Áno, pane?"), "pl": ("Polski", "Tak, proszę pana?"), "ru": ("Русский", "Да, сэр?"),
    "uk": ("Українська", "Так, сер?"), "ar": ("العربية", "نعم يا سيدي؟"), "es": ("Español", "¿Sí, señor?"),
    "fr": ("Français", "Oui, monsieur ?"), "it": ("Italiano", "Sì, signore?"), "pt": ("Português", "Sim, senhor?"),
    "nl": ("Nederlands", "Ja, meneer?"), "tr": ("Türkçe", "Evet efendim?"), "hu": ("Magyar", "Igen, uram?"),
    "ro": ("Română", "Da, domnule?"), "bg": ("Български", "Да, сър?"), "hr": ("Hrvatski", "Da, gospodine?"),
    "el": ("Ελληνικά", "Ναι, κύριε;"), "sv": ("Svenska", "Ja, sir?"), "da": ("Dansk", "Ja, sir?"),
    "no": ("Norsk", "Ja, sir?"), "fi": ("Suomi", "Niin, herra?"), "zh": ("中文", "先生，您好？"),
    "ja": ("日本語", "はい、何でしょう？"), "ko": ("한국어", "네, 말씀하세요?"), "hi": ("हिन्दी", "जी, सर?"),
    "id": ("Bahasa Indonesia", "Ya, Pak?"), "ms": ("Bahasa Melayu", "Ya, tuan?"), "fil": ("Filipino", "Opo, sir?"),
    "vi": ("Tiếng Việt", "Vâng, thưa ngài?"), "ta": ("தமிழ்", "சொல்லுங்கள், சார்?"),
}
LANG_KEY = "assistant.language"
ADDRESS_KEY = "assistant.address"
ADDRESS = {
    "sir": "Sprich ihn mit \"Sir\" an (in seiner Sprache die passende höfliche Anrede) und sieze ihn, nie mit seinem "
           "Namen -- so wie ein Butler, der seinen Chef mag: natürlich eingestreut, nicht in jedem Satz.",
    "name": "Sprich ihn mit seinem Namen Brano an und duze ihn -- wie ein guter Freund, nicht in jedem Satz.",
}


def language() -> str:
    code = _get(LANG_KEY, "de")
    return code if code in LANGS else "de"


def set_language(lang: str) -> dict:
    """lang: a code (cs) or a name in any form (Tschechisch, Čeština, czech)."""
    w = (lang or "").strip().lower()
    names = {"deutsch": "de", "german": "de", "englisch": "en", "english": "en", "tschechisch": "cs", "czech": "cs",
             "slowakisch": "sk", "slovak": "sk", "polnisch": "pl", "polish": "pl", "russisch": "ru", "russian": "ru",
             "ukrainisch": "uk", "arabisch": "ar", "arabic": "ar", "spanisch": "es", "französisch": "fr", "italienisch": "it",
             "portugiesisch": "pt", "niederländisch": "nl", "holländisch": "nl", "türkisch": "tr", "ungarisch": "hu",
             "rumänisch": "ro", "bulgarisch": "bg", "kroatisch": "hr", "griechisch": "el", "schwedisch": "sv",
             "dänisch": "da", "norwegisch": "no", "finnisch": "fi", "chinesisch": "zh", "japanisch": "ja",
             "koreanisch": "ko", "indisch": "hi", "hindi": "hi", "indonesisch": "id", "malaiisch": "ms",
             "philippinisch": "fil", "vietnamesisch": "vi", "tamil": "ta"}
    code = w if w in LANGS else names.get(w) or next((k for k, (n, _) in LANGS.items() if n.lower() == w), None)
    if not code:
        raise PersonaError(f"keine Sprache {lang!r}; es gibt {', '.join(n for n, _ in LANGS.values())}")
    _put(LANG_KEY, code)
    return {"language": code, "name": LANGS[code][0]}


def address() -> dict:
    a = _get(ADDRESS_KEY, {"style": "sir"})
    return a if a.get("style") in ("sir", "name", "custom") else {"style": "sir"}


def set_address(style: str, text: str = "") -> dict:
    if style not in ("sir", "name", "custom"):
        raise PersonaError("Anrede: sir, name oder custom")
    if style == "custom" and not text.strip():
        raise PersonaError("eigene Anrede braucht einen Text, z. B. 'Boss, du'")
    a = {"style": style, **({"text": text.strip()[:120]} if style == "custom" else {})}
    _put(ADDRESS_KEY, a)
    return a


def address_line() -> str:
    a = address()
    if a["style"] == "custom":
        return f"Sprich ihn so an: {a['text']} -- natürlich eingestreut, nicht in jedem Satz."
    return ADDRESS[a["style"]]
