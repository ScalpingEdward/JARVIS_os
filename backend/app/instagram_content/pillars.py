"""The account's five pillars -- Trading, Portrait, Gym, Essen, Travel -- and the rule that the feed
never shows the same one twice in a row (CLAUDE.md, Content-Strategie).

A pillar is read from what the vision analysis already wrote (theme and tags), so the 349 items
already in the pool have one without a single new analysis. Brano's own choice (item.pillar) wins.
An item that matches nothing has no pillar and never blocks anything.
"""
from __future__ import annotations

import re
from collections import Counter

PILLARS = ("Trading", "Gym", "Essen", "Portrait", "Travel")   # also the tie-break order
_WORDS = {
    "Trading": {"trading", "trader", "chart", "charts", "monitor", "monitors", "laptop", "desk", "home-office", "screen", "screens",
                "keyboard", "setup", "office"},
    "Gym": {"gym", "fitness", "workout", "weights", "barbell", "dumbbell", "dumbbells", "sambo", "locker", "training", "boxing",
            "fitness-equipment", "sports", "martial"},
    "Essen": {"food", "coffee", "steak", "breakfast", "restaurant", "dining", "plate", "dinner", "lunch", "dessert", "sushi",
              "casual-dining", "cocktail", "champagne", "wine", "cafe", "outdoor-cafe"},
    "Portrait": {"selfie", "portrait", "mirror-selfie", "casual-portrait", "beard", "headshot", "close-up"},
    "Travel": {"travel", "beach", "ocean", "airport", "airplane", "aviation", "landscape", "palm-trees", "seaside", "coastal",
               "mountain", "mountains", "snow", "hotel", "vacation", "cityscape", "bridge", "tourists", "mediterranean", "island",
               "sunset", "aerial-view", "pool", "poolside", "harbor", "promenade", "zoo", "wildlife", "nature",
               "forest", "river", "lake", "urban", "street-photography", "rooftop", "coastline", "luggage"},
}


def derive(theme: str, tags: list[str]) -> str | None:
    words = {t.lower().strip() for t in tags} | {t.lower().replace(" ", "-") for t in tags}
    words |= set(re.split(r"[-_\s]+", theme.lower())) | {theme.lower()}
    hits = {p: len(words & _WORDS[p]) for p in PILLARS}
    best = max(hits.values())
    return next(p for p in PILLARS if hits[p] == best) if best else None


def pillar_of(item) -> str | None:
    return getattr(item, "pillar", None) or derive(item.theme, item.tags)


def group_pillar(items) -> str | None:
    """A post's pillar: what most of its pictures are (the hook breaks a tie)."""
    found = [p for p in (pillar_of(i) for i in items) if p]
    if not found:
        return None
    counts = Counter(found)
    top = max(counts.values())
    first = pillar_of(items[0])
    return first if counts.get(first) == top else next(p for p in found if counts[p] == top)


def pick_next(drafts: list, pillar_for, last_pillar: str | None):
    """The queue's first draft -- unless it repeats the last post's pillar and the SAME shoot day
    has another one: then that one goes first. Day order is never broken for it."""
    if not drafts or not last_pillar:
        return drafts[0] if drafts else None
    day = drafts[0].content_day
    for d in drafts:
        if d.content_day != day:
            break
        if pillar_for(d) != last_pillar:
            return d
    return drafts[0]
