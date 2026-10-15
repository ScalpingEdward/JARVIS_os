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

    Deliberately NOT keyed on captured_at. That used to be one of the
    reasons here, back when a video's placeholder entry always had all
    three fields missing together (empty tags, placeholder theme, no
    captured_at) and the three were indistinguishable in practice. Frame
    extraction broke that: a Drive-sourced video can now get a real,
    paid-for vision analysis (real theme, real tags) while still
    structurally having no captured_at, because the n8n workflow never
    sends video_creation_time or upload_time for it. With captured_at in
    this list, every one of those real analyses counted as "incomplete"
    forever -- MediaPoolService.ingest() treated the freshly analyzed
    result as "no better than the placeholder already there" and silently
    discarded it, and analyze_and_ingest() kept re-submitting the same
    media_ref for analysis on every run since it never became "complete".
    30 real Anthropic vision calls were paid for and thrown away this way
    before this was caught. captured_at is a real gap worth closing
    (chronological curation needs it), but it is a missing-metadata
    problem, not evidence that the analysis itself did not happen -- so it
    does not belong in this function.
    """
    reasons: list[str] = []

    if not item.tags:
        reasons.append("tags are empty")

    theme = (item.theme or "").strip().lower()
    media_type = getattr(item.media_type, "value", item.media_type)
    if not theme or theme in PLACEHOLDER_THEMES or theme == str(media_type).lower():
        reasons.append(f"theme is a placeholder ({item.theme!r})")

    return reasons


def analysis_is_complete(item: _AnalyzableMedia) -> bool:
    return not analysis_incompleteness_reasons(item)
