"""A Reel that is longer than the account aims for must not slip through
silently.

Nothing in this system cuts a video file: n8n's image has no ffmpeg, and the
backend has no way to put a re-encoded file somewhere Instagram can fetch it.
So the honest behaviour is to say so at the moment a human decides, and to
name the segment AURON's frame analysis actually picked -- not to imply a
trim is about to happen.

The bug this locks down: "too long" was defined twice. The ingest step
analyzed a trim window against the 30s the account aims for, and the edit
plan then judged the same clip against Instagram's 90s ceiling and marked it
"no trim needed". A 46s clip therefore carried a real, paid-for trim window
and produced no warning at all.
"""

from __future__ import annotations

import pytest

from app.instagram_content.format_decision import REEL_PLATFORM_MAX_SECONDS, reel_duration_notes
from app.instagram_content.edit_plan import build_edit_plan
from app.instagram_content.models import ContentCandidateCreate, MediaItem, PostFormat
from app.instagram_content.reel_targets import target_max_seconds, target_min_seconds
from app.instagram_content.service import InstagramContentService

CAPTION = "The sea keeps its own time. #travel #coast #stillness"


def _video(duration: float, **overrides) -> MediaItem:
    payload = dict(media_ref="clip", media_type="video", aesthetic_score=0.6, duration_seconds=duration)
    payload.update(overrides)
    return MediaItem(**payload)


@pytest.fixture(autouse=True)
def _clean():
    InstagramContentService().reset()
    yield


def test_a_clip_inside_the_target_range_says_nothing():
    assert reel_duration_notes(_video(20.0)) == []


def test_the_46_second_case_that_used_to_pass_unnoticed():
    """46s: over the 30s target, under the 90s ceiling. This exact clip
    produced no warning at all before the two thresholds were unified."""
    notes = reel_duration_notes(_video(46.0))

    assert len(notes) == 1
    assert "46s" in notes[0]
    assert f"{target_max_seconds():.0f}s" in notes[0]


def test_the_warning_names_the_real_analyzed_window_when_there_is_one():
    notes = reel_duration_notes(_video(
        46.0, recommended_trim_start_seconds=14.5, recommended_trim_end_seconds=41.2
    ))

    assert "14.5s-41.2s" in notes[0]


def test_the_warning_never_implies_something_will_cut_the_file():
    """The decisive wording. A note saying only "trimming is recommended"
    reads like a step that is about to run -- and none is."""
    notes = reel_duration_notes(_video(46.0))

    assert "Nothing here cuts the file" in notes[0]


def test_a_clip_over_the_platform_ceiling_is_called_what_it_is():
    """Past 90s it is not a preference anymore -- Instagram refuses it."""
    notes = reel_duration_notes(_video(REEL_PLATFORM_MAX_SECONDS + 5))

    assert "ceiling" in notes[0]
    assert "refuse" in notes[0]


def test_a_clip_under_the_target_floor_is_flagged_too():
    notes = reel_duration_notes(_video(4.0))

    assert f"{target_min_seconds():.0f}s" in notes[0]


def test_an_image_is_never_judged_on_duration():
    assert reel_duration_notes(MediaItem(media_ref="p", media_type="image", aesthetic_score=0.6)) == []


def test_the_edit_plan_and_the_ingest_step_now_use_one_yardstick():
    """The actual defect: these disagreed, so a clip could carry an analyzed
    trim window and still be marked as needing no trim."""
    over_target = target_max_seconds() + 16.0
    assert over_target < REEL_PLATFORM_MAX_SECONDS, "the gap between the two thresholds is the point"

    plan = build_edit_plan([_video(over_target)], PostFormat.reel)

    assert plan[0].trim_needed is True


def test_the_warning_reaches_the_candidate_a_human_approves():
    """It has to sit on the candidate itself, next to the other warnings --
    not buried in edit_plan[].notes where nobody looks while deciding."""
    service = InstagramContentService()
    candidate = service.propose(ContentCandidateCreate(
        media_items=[_video(46.0, recommended_trim_start_seconds=14.5, recommended_trim_end_seconds=41.2)],
        caption_draft=CAPTION,
    ))

    assert candidate.post_format == PostFormat.reel
    assert len(candidate.edit_warnings) == 1
    assert "14.5s-41.2s" in candidate.edit_warnings[0]
    assert any("Edit warnings" in line for line in candidate.audit_log)

    stored = service.get(candidate.id)
    assert stored.edit_warnings == candidate.edit_warnings, "must survive storage, not just the response"


def test_a_post_within_range_carries_no_warning_noise():
    service = InstagramContentService()
    candidate = service.propose(ContentCandidateCreate(
        media_items=[_video(20.0)], caption_draft=CAPTION,
    ))

    assert candidate.edit_warnings == []
