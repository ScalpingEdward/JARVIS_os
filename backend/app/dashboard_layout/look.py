"""The dashboard's look -- colours, glass, clock, planet, room, and each card's text -- in AURON's
database, so it is the same on every screen and AURON can change it on Brano's word.

Every dashboard asks every 2 s whether the version moved and takes the new look over (look.js);
a change made by hand in the settings comes back here the same way. The ten looks before the
current one are kept, so "zurück" undoes AURON's last change -- or Brano's.
"""
from __future__ import annotations

from .service import LayoutError, _write
from .service import _read as _read_row


def _read(key: str):
    return _read_row(key)[0]

KEY, HISTORY_KEY = "dashboard.look", "dashboard.look.history"
KEEP = 10

# what may be set, for AURON's tool and to refuse nonsense (frontend/settings.js, cardview.js, rooms.js)
CATALOG = {
    "theme": {
        "accent": ["#4fd8ff Cyan", "#f5b84a Gold", "#ff7eb6 Rosa", "#3ddc97 Grün", "#b88cff Lila", "#f2f4f8 Weiß", "or any #rrggbb"],
        "tint": ["#96c8ff Eisblau", "#ffd28c Champagner", "#ffb4d2 Rosé", "#b4ffd2 Mint", "#d2b4ff Flieder", "#e6e6e6 Neutral",
                 "#000000 Schwarz", "#26292f Graphit", "#0b1630 Nachtblau", "or any #rrggbb -- the glass colour of the cards"],
        "style": ["clear Klar", "frosted Matt", "faded Verblasst", "solid Massiv"],
        "strength": "20..200 (glass strength in %)",
        "clock": ["clean Klar", "thin Dünn", "mono Digital", "elegant Elegant", "neon Neon", "bold Fett"],
        "clockSize": "40..120 (px)",
        "clockColor": ["#ffffff Weiß", "accent", "#f5b84a Gold", "#ff7eb6 Rosa", "#3ddc97 Grün", "#9fb0c8 Grau", "or any #rrggbb"],
        "planet": ["#4fd8ff Cyan", "#f5b84a Gold", "#ff7eb6 Rosa", "#3ddc97 Grün", "#b88cff Lila", "#ff5a5a Rot", "#e8e8e8 Silber"],
        "core": ["planet Planet", "bare Ohne Ringe", "rings Nur Ringe", "off Aus"],
    },
    "room": ["lounge Lounge bei Nacht", "noir Noir", "gold Gold", "orbit Orbit", "alps Alpen bei Sonnenuntergang",
             "earth Über der Erde", "forest Wald mit Wasserfall", "earth2 Orbit-Lounge", "clouds Über den Wolken", "ocean Unter Wasser"],
    "cards": {
        "ids": ["tileTrading Trading", "tileWatch Watchlist", "tileInstagram Instagram", "tileMail Post", "tileSmart Smart Money", "all"],
        "size": [0.9, 1, 1.12, 1.25, 1.4, 1.55],
        "num": [0.9, 1, 1.12, 1.25, 1.4, 1.55],
        "font": ["std Standard", "exo Exo 2", "rajdhani Rajdhani", "sora Sora", "oxanium Oxanium", "manrope Manrope"],
        "view": ["list Liste", "tiles Kacheln"],
    },
}
CARD_IDS = [c.split()[0] for c in CATALOG["cards"]["ids"] if c != "all"]
_CHOICES = {k: {v.split()[0] for v in vals if not v.startswith("or ")} for k, vals in CATALOG["theme"].items() if isinstance(vals, list)}
_FREE_COLOUR = {"accent", "tint", "clockColor", "planet"}
_ROOMS = {r.split()[0] for r in CATALOG["room"]}
_FONTS = {f.split()[0] for f in CATALOG["cards"]["font"]}


def get() -> dict:
    return _read(KEY) or {"version": 0, "look": {}}


def _is_colour(v) -> bool:
    return isinstance(v, str) and len(v) == 7 and v[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in v[1:])


def _check_theme(theme: dict) -> dict:
    out = {}
    for k, v in theme.items():
        if k in ("strength", "clockSize"):
            lo, hi = (20, 200) if k == "strength" else (40, 120)
            if not isinstance(v, (int, float)) or not lo <= v <= hi:
                raise LayoutError(f"{k} must be {lo}..{hi}")
        elif k in _CHOICES:
            if v not in _CHOICES[k] and not (k in _FREE_COLOUR and _is_colour(v)):
                raise LayoutError(f"{k}={v!r} is not one of {sorted(_CHOICES[k])}")
        else:
            raise LayoutError(f"unknown design setting {k!r}")
        out[k] = v
    return out


def _check_card(st: dict) -> dict:
    out = {}
    for k, v in st.items():
        if k in ("size", "num") and v not in CATALOG["cards"][k]:
            raise LayoutError(f"card {k} must be one of {CATALOG['cards'][k]}")
        if k == "font" and v not in _FONTS:
            raise LayoutError(f"font must be one of {sorted(_FONTS)}")
        if k == "view" and v not in ("list", "tiles"):
            raise LayoutError("view must be list or tiles")
        if k not in ("size", "num", "font", "view"):
            raise LayoutError(f"unknown card setting {k!r}")
        out[k] = v
    return out


def _store(look: dict, by: str) -> dict:
    cur = get()
    if cur["look"]:
        hist = (_read(HISTORY_KEY) or [])[-(KEEP - 1):]
        _write(HISTORY_KEY, hist + [cur["look"]])
    new = {"version": cur["version"] + 1, "look": look, "by": by}
    _write(KEY, new)
    return new


def save(look: dict, by: str = "dashboard") -> dict:
    """The whole look from a dashboard (a change by hand). A phone sends no cards: those stay."""
    cur = get()["look"]
    theme = _check_theme(look.get("theme") or {}) or cur.get("theme", {})
    room = look.get("room") or cur.get("room")
    if room and room not in _ROOMS:
        raise LayoutError(f"room must be one of {sorted(_ROOMS)}")
    cards = {cid: _check_card(st) for cid, st in (look.get("cards") or {}).items() if cid in CARD_IDS} \
        if "cards" in look else cur.get("cards", {})
    new = {"theme": theme, "room": room, "cards": cards}
    if new == cur:
        return get()
    return _store(new, by)


def change(theme: dict | None = None, room: str | None = None, card: str | None = None,
           card_style: dict | None = None, by: str = "auron") -> dict:
    """A part of the look, the rest stays: theme keys, the room, one card's (or all cards') text."""
    cur = get()["look"]
    new = {"theme": {**cur.get("theme", {}), **_check_theme(theme or {})},
           "room": cur.get("room"), "cards": {k: dict(v) for k, v in cur.get("cards", {}).items()}}
    if room:
        if room not in _ROOMS:
            raise LayoutError(f"room must be one of {sorted(_ROOMS)}")
        new["room"] = room
    if card_style:
        st = _check_card(card_style)
        if card in (None, "", "all"):
            targets = CARD_IDS
        else:
            q = card.lower()
            targets = [c for c in CATALOG["cards"]["ids"] if c != "all" and q in c.lower()]
            targets = [t.split()[0] for t in targets]
            if not targets:
                raise LayoutError(f"no card {card!r}; cards: {CATALOG['cards']['ids']}")
        for cid in targets:
            new["cards"][cid] = {**new["cards"].get(cid, {}), **st}
    if new == cur:
        return get()
    return _store(new, by)


def undo() -> dict:
    hist = _read(HISTORY_KEY) or []
    if not hist:
        raise LayoutError("nothing to undo")
    prev = hist.pop()
    _write(HISTORY_KEY, hist)
    new = {"version": get()["version"] + 1, "look": prev, "by": "undo"}
    _write(KEY, new)
    return new
