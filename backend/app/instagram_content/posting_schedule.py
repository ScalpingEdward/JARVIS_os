from __future__ import annotations

from dataclasses import dataclass

# General high-engagement windows (local time, weekday), well-documented
# Instagram usage patterns -- NOT derived from this account's own Insights
# data, which AURON has no access to yet. Treat as a reasonable starting
# point, not a data-backed schedule; replace with real per-account
# analytics once the Instagram Insights API is wired (it isn't).
_GENERIC_WINDOWS = {
    0: [(11, 13), (19, 21)],  # Monday
    1: [(11, 13), (19, 21)],  # Tuesday
    2: [(11, 13), (19, 21)],  # Wednesday
    3: [(11, 13), (19, 22)],  # Thursday
    4: [(11, 14), (17, 21)],  # Friday
    5: [(10, 13)],  # Saturday
    6: [(10, 13), (18, 20)],  # Sunday
}


@dataclass(frozen=True)
class PostingWindow:
    weekday: int  # 0=Monday
    start_hour: int
    end_hour: int


def suggested_windows_for_weekday(weekday: int) -> list[PostingWindow]:
    if weekday not in _GENERIC_WINDOWS:
        raise ValueError(f"weekday must be 0-6 (Monday-Sunday), got {weekday}")
    return [PostingWindow(weekday=weekday, start_hour=s, end_hour=e) for s, e in _GENERIC_WINDOWS[weekday]]


NOTE = (
    "These windows are general, well-documented Instagram usage patterns, not this "
    "account's own analytics -- there is no Instagram Insights integration yet. Treat "
    "as a starting default, not a data-backed schedule."
)
