"""The hashtags this account is allowed to use.

Left to itself the caption writer invents mood words -- #QuietWealth,
#StillWaters, #stillness -- which read well and are searched by nobody. A
hashtag here is a topic label, not a phrase: it only does its job if real
people actually browse it.

So the model no longer invents them. It picks from this list, and a caption
carrying anything else is rewritten. The list is maintained by hand (Brano
approved this set on 2026-09-23, English on purpose: a wider audience than
German tags reach) -- editing it is the one place where the account's tags
change, instead of a different guess per post.
"""

from __future__ import annotations

#: By pillar, matching the content strategy in CLAUDE.md. Trading carries
#: the account; the rest are support columns and need a link back to it.
ALLOWED_BY_PILLAR: dict[str, tuple[str, ...]] = {
    "trading": (
        "#trading", "#forex", "#daytrading", "#priceaction",
        "#smartmoneyconcepts", "#tradingpsychology", "#forextrader", "#chartanalysis",
    ),
    "gym": ("#gym", "#calisthenics", "#strengthtraining", "#fitnessjourney", "#homeworkout"),
    "food": ("#healthyfood", "#highprotein", "#mealprep", "#cleaneating"),
    "travel": ("#travel", "#dubai", "#travelphotography", "#vanlife"),
    "portrait": ("#portrait", "#mensstyle", "#lifestyle", "#mindset", "#discipline"),
}

ALLOWED: frozenset[str] = frozenset(tag for tags in ALLOWED_BY_PILLAR.values() for tag in tags)


def normalize(tag: str) -> str:
    return tag.strip().lower()


def unknown_tags(tags: list[str]) -> list[str]:
    """Which of these are not on the list. Case is ignored -- #Trading and
    #trading are the same label to Instagram."""
    return [tag for tag in tags if normalize(tag) not in ALLOWED]


def prompt_block() -> str:
    lines = [f"{pillar}: {' '.join(tags)}" for pillar, tags in ALLOWED_BY_PILLAR.items()]
    return "\n".join(lines)
