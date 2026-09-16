from __future__ import annotations

from typing import Protocol, Sequence

#: Theme labels that carry no information about what is actually in the frame.
#: They are what a fallback path writes when no vision analysis ran, not
#: something the vision step would ever produce.
PLACEHOLDER_THEMES = frozenset({"video", "image", "unknown", ""})


class _AnalyzableMedia(Protocol):
    """Whatever carries the analysis fields -- MediaPoolItem, or a
    MediaPoolItemCreate that has not been persisted yet."""

    theme: str
    tags: Sequence[str]
    media_type: object


def analysis_incompleteness_reasons(item: _AnalyzableMedia) -> list[str]:
    """Why this item's analysis does not count as real, or an empty list if
    it does.

    This is the single definition of "incomplete" in the system. The media
    pool endpoint exposes the verdict as `analysis_complete`, the ingest
    path uses it to decide whether a known media_ref may be re-analyzed,
    and the n8n ingest workflow reads the field rather than re-deriving the
    rule -- so the rule lives here and nowhere else.

    Deliberately not keyed on media_type: a video whose frames were
    analyzed is complete, and an image whose analysis silently failed is
    not. Adding a rule means adding one line here.
    """
    reasons: list[str] = []

    if not item.tags:
        reasons.append("tags are empty")

    if getattr(item, "captured_at", None) is None:
        reasons.append("captured_at is missing")

    theme = (item.theme or "").strip().lower()
    media_type = getattr(item.media_type, "value", item.media_type)
    if not theme or theme in PLACEHOLDER_THEMES or theme == str(media_type).lower():
        reasons.append(f"theme is a placeholder ({item.theme!r})")

    return reasons


def analysis_is_complete(item: _AnalyzableMedia) -> bool:
    return not analysis_incompleteness_reasons(item)
