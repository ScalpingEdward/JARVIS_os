from pathlib import Path

import pytest

from app.content.auron_instagram_content_lifecycle_v21_541 import ContentLifecycleError, InstagramContentLifecycle
from app.content.auron_instagram_registry_calendar_v21_540 import Brand, InstagramAccount, InstagramContentRegistryCalendar
from app.core.auron_integration_readiness_v21_541 import get_integration_readiness


def stack(tmp_path: Path):
    db = tmp_path / 'content.sqlite3'
    registry = InstagramContentRegistryCalendar(db)
    registry.upsert_brand(Brand('brand-1', 'AURON Media', 'Europe/Berlin', 'de'))
    registry.register_account(InstagramAccount('ig-1', 'brand-1', '@auron.media', None, 'active'))
    registry.add_calendar_entry(content_id='c-1', brand_id='brand-1', account_id='ig-1',
                                content_type='reel', title='Launch Reel')
    lifecycle = InstagramContentLifecycle(db, registry)
    return registry, lifecycle


def test_initialize_creates_first_immutable_revision(tmp_path: Path) -> None:
    _, lifecycle = stack(tmp_path)
    record = lifecycle.initialize('c-1', caption='Hello', hashtags=('#AI', 'ai', '#Jarvis'),
                                  asset_uris=('file://reel.mp4',), creative_notes='Fast hook',
                                  actor='operator', reason='first draft')
    assert record.state == 'idea'
    assert record.current_version == 1
    history = lifecycle.revision_history('c-1')
    assert len(history) == 1
    assert history[0].hashtags == ('AI', 'Jarvis')
    assert history[0].integrity_hash


def test_revisions_append_and_do_not_overwrite_prior_version(tmp_path: Path) -> None:
    _, lifecycle = stack(tmp_path)
    lifecycle.initialize('c-1', caption='v1', actor='operator', reason='initial')
    first = lifecycle.get_revision('c-1', 1)
    second = lifecycle.add_revision('c-1', caption='v2', hashtags=('growth',),
                                    actor='operator', reason='improve hook')
    assert second.version == 2
    assert lifecycle.get_revision('c-1', 1) == first
    assert lifecycle.get_revision('c-1', 1).caption == 'v1'
    assert lifecycle.get_revision('c-1', 2).caption == 'v2'


def test_lifecycle_requires_valid_sequence_and_schedule_timestamp(tmp_path: Path) -> None:
    registry, lifecycle = stack(tmp_path)
    lifecycle.initialize('c-1', caption='draft', actor='operator', reason='initial')
    with pytest.raises(ContentLifecycleError, match='invalid lifecycle transition'):
        lifecycle.transition('c-1', 'approved')
    lifecycle.transition('c-1', 'draft')
    lifecycle.transition('c-1', 'review')
    lifecycle.transition('c-1', 'approved')
    with pytest.raises(ContentLifecycleError, match='scheduled_for'):
        lifecycle.transition('c-1', 'scheduled')
    scheduled = lifecycle.transition('c-1', 'scheduled', scheduled_for='2026-08-20T18:00:00+02:00')
    assert scheduled.state == 'scheduled'
    calendar = registry.get_calendar_entry('c-1')
    assert calendar.state == 'scheduled'
    assert calendar.scheduled_for == '2026-08-20T18:00:00+02:00'


def test_publishing_is_internal_state_only_and_result_requires_value(tmp_path: Path) -> None:
    registry, lifecycle = stack(tmp_path)
    lifecycle.initialize('c-1', caption='draft', actor='operator', reason='initial')
    lifecycle.transition('c-1', 'draft')
    lifecycle.transition('c-1', 'review')
    lifecycle.transition('c-1', 'approved')
    lifecycle.transition('c-1', 'scheduled', scheduled_for='2026-08-20T18:00:00+02:00')
    publishing = lifecycle.transition('c-1', 'publishing')
    assert publishing.state == 'publishing'
    assert publishing.external_calls_made == 0
    with pytest.raises(ContentLifecycleError, match='publish_result'):
        lifecycle.transition('c-1', 'result')
    result = lifecycle.transition('c-1', 'result', publish_result='published')
    assert result.publish_result == 'published'
    assert registry.get_calendar_entry('c-1').state == 'published'


def test_metadata_locks_once_publishing_begins(tmp_path: Path) -> None:
    _, lifecycle = stack(tmp_path)
    lifecycle.initialize('c-1', caption='draft', actor='operator', reason='initial')
    lifecycle.transition('c-1', 'draft')
    lifecycle.transition('c-1', 'review')
    lifecycle.transition('c-1', 'approved')
    lifecycle.transition('c-1', 'scheduled', scheduled_for='2026-08-20T18:00:00+02:00')
    lifecycle.transition('c-1', 'publishing')
    with pytest.raises(ContentLifecycleError, match='locked'):
        lifecycle.add_revision('c-1', caption='late edit', actor='operator', reason='too late')


def test_c2_advances_exactly_to_c3() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.541'
    assert readiness['current_item'] == 'C2-content-lifecycle-version-history'
    assert readiness['next_item'] == 'C3-meta-instagram-read-health-adapter'
    assert readiness['instagram_provider_connected'] is False
    assert readiness['instagram_publishing_enabled'] is False
    assert readiness['external_calls_made'] == 0
