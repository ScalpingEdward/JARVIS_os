from __future__ import annotations

import re

from .models import ContentCandidateCreate
from .platform_strategy import platform_strategy_store

# Deliberately explicit and editable in one place, not scattered constants --
# this is the account's brand/compliance policy, not a technical detail.
# Hashtag cap/range and aesthetic thresholds now live in platform_strategy.py
# (dynamically updatable via researched proposals, applied only explicitly);
# MAX_CAPTION_LENGTH is Instagram's own fixed API limit and never changes.
MAX_CAPTION_LENGTH = 2200  # Instagram's own hard limit

BANNED_PHRASES = (
    "follow4follow",
    "f4f",
    "like4like",
    "l4l",
    "sub4sub",
    "click the link in bio now",
    "dm for promo",
    "guaranteed followers",
)

_HASHTAG_RE = re.compile(r"#\w+")


class ModerationResult:
    def __init__(self, violations: list[str] | None = None, warnings: list[str] | None = None) -> None:
        self.violations = violations or []
        self.warnings = warnings or []

    @property
    def passed(self) -> bool:
        return not self.violations


def moderate(candidate: ContentCandidateCreate, recent_captions: list[str]) -> ModerationResult:
    """Runs explicit, deterministic policy checks before a candidate ever
    reaches a human for approval. Violations auto-reject (never shown to
    the human as pending); warnings still go to human review, just flagged.

    This exists so review time goes to real judgment calls (does this fit
    the aesthetic, is the caption's voice right) instead of catching
    spam-pattern captions or duplicate posts by hand every time.
    """
    violations: list[str] = []
    warnings: list[str] = []

    strategy = platform_strategy_store.current()

    caption = candidate.caption_draft.strip()
    if not caption:
        violations.append("Caption is empty.")
    if len(caption) > MAX_CAPTION_LENGTH:
        violations.append(f"Caption exceeds Instagram's {MAX_CAPTION_LENGTH}-character limit.")

    hashtags = _HASHTAG_RE.findall(caption)
    if len(hashtags) > strategy.max_hashtags:
        violations.append(
            f"{len(hashtags)} hashtags exceeds Instagram's platform-enforced {strategy.max_hashtags}-hashtag cap "
            "(publish-time restriction, not just a style guideline)."
        )
    elif len(hashtags) == 0:
        warnings.append(
            "No hashtags at all -- even though hashtags no longer drive reach directly, they still help "
            "Instagram categorize the post correctly; a missed classification signal."
        )
    elif len(hashtags) < strategy.optimal_hashtag_min:
        warnings.append(
            f"Only {len(hashtags)} hashtag(s); current guidance is "
            f"{strategy.optimal_hashtag_min}-{strategy.optimal_hashtag_max} for the clearest categorization signal."
        )

    lowered = caption.lower()
    hit_phrases = [phrase for phrase in BANNED_PHRASES if phrase in lowered]
    if hit_phrases:
        violations.append(f"Caption contains spam-pattern phrase(s): {', '.join(hit_phrases)}.")

    scores = [item.aesthetic_score for item in candidate.media_items]
    average_score = sum(scores) / len(scores)
    weakest_score = min(scores)
    # NOTE: aesthetic score thresholds are curation's ELITE_SOLO_THRESHOLD-adjacent
    # concept but a separate, lower bar for "acceptable at all" -- kept as fixed
    # values here (not in PlatformStrategy) since they're account-taste calls,
    # not platform-rule facts a web search can verify.
    min_aesthetic_hard = 0.35
    min_aesthetic_soft = 0.6
    if average_score < min_aesthetic_hard:
        violations.append(
            f"Average aesthetic score {average_score:.2f} is below the account's minimum bar ({min_aesthetic_hard})."
        )
    elif average_score < min_aesthetic_soft:
        warnings.append(
            f"Average aesthetic score {average_score:.2f} is below the usual bar "
            f"({min_aesthetic_soft}) -- borderline fit for the account."
        )
    if len(scores) > 1 and weakest_score < min_aesthetic_hard:
        warnings.append(
            f"At least one media item scores {weakest_score:.2f}, below the account's minimum bar -- "
            "consider dropping it from the carousel even if the average is fine."
        )

    if caption in recent_captions:
        violations.append("This exact caption was already proposed recently (near-duplicate content).")

    return ModerationResult(violations=violations, warnings=warnings)
