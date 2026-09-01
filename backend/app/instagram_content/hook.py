from __future__ import annotations

# Instagram truncates captions in-feed at roughly this many characters
# before "...more" -- the hook has to land before that cutoff or it never
# gets read.
FEED_TRUNCATION_CHARS = 125
MIN_HOOK_CHARS = 8


def check_hook(caption: str) -> list[str]:
    """Warnings about the caption's opening line as a hook. Deliberately
    warnings, not hard violations -- hook quality is a judgment call, not
    something to auto-reject on, unlike moderation.py's spam/policy checks."""
    warnings: list[str] = []
    first_line = caption.strip().split("\n", 1)[0].strip()

    if len(first_line) < MIN_HOOK_CHARS:
        warnings.append(f"Opening line is only {len(first_line)} chars -- likely too thin to stop a scroll.")

    if first_line.startswith("#"):
        warnings.append("Caption opens with a hashtag instead of a hook -- hashtags read as noise up front.")

    if len(first_line) > FEED_TRUNCATION_CHARS:
        warnings.append(
            f"Opening line is {len(first_line)} chars, past Instagram's ~{FEED_TRUNCATION_CHARS}-char "
            "in-feed truncation -- the actual hook may get cut off before '...more'."
        )

    if first_line and first_line == first_line.upper() and any(c.isalpha() for c in first_line):
        warnings.append("Opening line is all caps -- reads as shouting rather than confident.")

    return warnings
