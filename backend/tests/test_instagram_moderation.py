"""Tests for the automated pre-approval moderation gate (moderation.py + the
propose()/decide() wiring in service.py)."""

from __future__ import annotations

import pytest

from app.instagram_content.models import ContentCandidateCreate, ContentDecision, ContentStatus
from app.instagram_content.moderation import moderate
from app.instagram_content.service import InstagramContentService


def _payload(**overrides):
    base = dict(
        image_source_ref="drive://file-1",
        caption_draft="Build in silence. Let the results make the noise.",
        aesthetic_score=0.9,
    )
    base.update(overrides)
    return ContentCandidateCreate(**base)


# -- moderate() unit tests: deterministic, no service state involved --------


def test_moderate_passes_a_clean_candidate():
    result = moderate(_payload(), recent_captions=[])
    assert result.passed
    assert result.violations == []
    assert result.warnings == []


def test_moderate_rejects_too_many_hashtags():
    caption = "Quiet confidence. " + " ".join(f"#tag{i}" for i in range(31))
    result = moderate(_payload(caption_draft=caption), recent_captions=[])
    assert not result.passed
    assert any("hashtag" in v.lower() for v in result.violations)


def test_moderate_warns_when_close_to_the_hashtag_limit():
    caption = "Quiet confidence. " + " ".join(f"#tag{i}" for i in range(27))
    result = moderate(_payload(caption_draft=caption), recent_captions=[])
    assert result.passed
    assert any("hashtag" in w.lower() for w in result.warnings)


def test_moderate_rejects_spam_pattern_phrases():
    result = moderate(_payload(caption_draft="Follow4follow, DM for promo!"), recent_captions=[])
    assert not result.passed
    assert any("spam" in v.lower() for v in result.violations)


def test_moderate_rejects_low_aesthetic_score():
    result = moderate(_payload(aesthetic_score=0.1), recent_captions=[])
    assert not result.passed
    assert any("aesthetic" in v.lower() for v in result.violations)


def test_moderate_warns_on_borderline_aesthetic_score():
    result = moderate(_payload(aesthetic_score=0.5), recent_captions=[])
    assert result.passed
    assert any("aesthetic" in w.lower() for w in result.warnings)


def test_moderate_rejects_near_duplicate_caption():
    caption = "Build in silence. Let the results make the noise."
    result = moderate(_payload(caption_draft=caption), recent_captions=[caption])
    assert not result.passed
    assert any("duplicate" in v.lower() for v in result.violations)


# -- service wiring: propose() actually applies moderation ------------------


def test_propose_auto_rejects_a_policy_violating_candidate():
    service = InstagramContentService()
    item = service.propose(_payload(caption_draft="Follow4follow please!!"))
    assert item.status == ContentStatus.moderation_rejected
    assert "Auto-rejected" in item.decision_reason
    assert item.id in {i.id for i in service.list_all(status=ContentStatus.moderation_rejected)}
    # never appears as something waiting on the human
    assert item.id not in {i.id for i in service.list_all(status=ContentStatus.proposed)}


def test_propose_attaches_warnings_but_still_reaches_proposed():
    service = InstagramContentService()
    item = service.propose(_payload(aesthetic_score=0.5))
    assert item.status == ContentStatus.proposed
    assert item.moderation_warnings != []


def test_human_can_override_a_moderation_rejection():
    service = InstagramContentService()
    item = service.propose(_payload(caption_draft="Follow4follow please!!"))
    assert item.status == ContentStatus.moderation_rejected

    overridden = service.decide(item.id, ContentDecision(approved=True, reason="False positive, this is fine"))
    assert overridden.status == ContentStatus.approved
    assert any("override" in entry.lower() for entry in overridden.audit_log)


def test_second_identical_caption_is_caught_as_duplicate_by_the_running_service():
    service = InstagramContentService()
    caption = "Quiet confidence. Nothing to prove."
    first = service.propose(_payload(caption_draft=caption, image_source_ref="drive://a"))
    assert first.status == ContentStatus.proposed

    second = service.propose(_payload(caption_draft=caption, image_source_ref="drive://b"))
    assert second.status == ContentStatus.moderation_rejected
