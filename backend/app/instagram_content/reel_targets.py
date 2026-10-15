from __future__ import annotations

import os

#: What counts as "the right length for a Reel". Deliberately configurable
#: rather than hard-coded: this is a content-strategy decision, not a
#: property of the code, and it changes when the strategy does.
#:
#: A video longer than the maximum is the only case where AURON runs a trim
#: analysis during ingest -- for anything already within range there is
#: nothing to cut and no reason to spend the call.
_TARGET_MIN_ENV = "AURON_REEL_TARGET_MIN_SECONDS"
_TARGET_MAX_ENV = "AURON_REEL_TARGET_MAX_SECONDS"

DEFAULT_TARGET_MIN_SECONDS = 15.0
DEFAULT_TARGET_MAX_SECONDS = 30.0


def _read(name: str, fallback: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return fallback
    try:
        value = float(raw)
    except ValueError:
        return fallback
    return value if value > 0 else fallback


def target_min_seconds() -> float:
    return _read(_TARGET_MIN_ENV, DEFAULT_TARGET_MIN_SECONDS)


def target_max_seconds() -> float:
    return _read(_TARGET_MAX_ENV, DEFAULT_TARGET_MAX_SECONDS)


def needs_trim(duration_seconds: float) -> bool:
    return duration_seconds > target_max_seconds()
