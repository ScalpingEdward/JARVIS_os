from pathlib import Path

import pytest

from app.content.auron_instagram_registry_calendar_v21_540 import (
    Brand,
    ContentRegistryError,
    InstagramAccount,
    InstagramContentRegistryCalendar,
)
from app.core.auron_integration_readiness_v21_540 import get_integration_readiness


def store(tmp_path: Path) -> InstagramContentRegistryCalendar:
    s = InstagramContentRegistryCalendar(tmp_path / 'content.sqlite3')
    s.upsert_brand(Brand('brand-1', 'AURON Media', 'Europe/Berlin', 'de'))
    s.register_account(InstagramAccount('ig-1', 'brand-1', '@auron.media', None, 'active'))
    return s


def test_brand_and_account_persist(tmp_path: Path) -> None:
    s = store(tmp_path)
    assert s.get_brand('brand-1').name == 'AURON Media'
    account = s.get_account('ig-1')
    assert account.handle == 'auron.media'
    assert account.publishing_enabled is False
    reopened = InstagramContentRegistryCalendar(tmp_path / 'content.sqlite3')
    assert reopened.get_account('ig-1').handle == 'auron.media'


def test_account_requires_existing_brand_and_publish_starts_disabled(tmp_path: Path) -> None:
    s = InstagramContentRegistryCalendar(tmp_path / 'content.sqlite3')
    with pytest.raises(ContentRegistryError, match='brand must exist'):
        s.register_account(InstagramAccount('ig-x', 'missing', 'x', None, 'active'))
    s.upsert_brand(Brand('b', 'Brand', 'UTC', 'en'))
    with pytest.raises(ContentRegistryError, match='publishing disabled'):
        s.register_account(InstagramAccount('ig-x', 'b', 'x', None, 'active', True))


def test_calendar_entry_is_brand_account_scoped(tmp_path: Path) -> None:
    s = store(tmp_path)
    entry = s.add_calendar_entry(
        content_id='content-1', brand_id='brand-1', account_id='ig-1',
        content_type='reel', title='First Reel', state='idea',
    )
    assert entry.state == 'idea'
    assert s.list_calendar(account_id='ig-1')[0].content_id == 'content-1'


def test_scheduled_entry_requires_time(tmp_path: Path) -> None:
    s = store(tmp_path)
    with pytest.raises(ContentRegistryError, match='scheduled_for'):
        s.add_calendar_entry(
            content_id='content-2', brand_id='brand-1', account_id='ig-1',
            content_type='post', title='Scheduled Post', state='scheduled',
        )


def test_snapshot_and_readiness_keep_provider_disabled(tmp_path: Path) -> None:
    s = store(tmp_path)
    snapshot = s.snapshot()
    assert snapshot['provider_connected'] is False
    assert snapshot['publishing_enabled'] is False
    assert snapshot['external_calls_made'] == 0

    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.540'
    assert readiness['current_item'] == 'C1-brand-account-registry-content-calendar'
    assert readiness['next_item'] == 'C2-content-lifecycle-version-history'
    assert readiness['instagram_provider_connected'] is False
    assert readiness['instagram_publishing_enabled'] is False
    assert readiness['external_calls_made'] == 0
