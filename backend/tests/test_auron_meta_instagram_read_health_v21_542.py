from datetime import datetime, timezone
from pathlib import Path

from app.content.auron_instagram_registry_calendar_v21_540 import Brand, InstagramAccount, InstagramContentRegistryCalendar
from app.content.auron_meta_instagram_read_health_v21_542 import (
    InMemoryMetaInstagramReadSource,
    MetaInstagramReadHealthAdapter,
    ProviderHealthSnapshot,
)
from app.core.auron_integration_readiness_v21_542 import get_integration_readiness


def setup_registry(tmp_path: Path, *, handle: str = 'auron.media', provider_ref: str | None = 'meta-123'):
    registry = InstagramContentRegistryCalendar(tmp_path / 'content.sqlite3')
    registry.upsert_brand(Brand('brand-1', 'AURON Media', 'Europe/Berlin', 'de'))
    registry.register_account(InstagramAccount('ig-1', 'brand-1', handle, provider_ref, 'active'))
    return registry


def health(*, username='auron.media', token='healthy', permission='healthy', permissions=('account.read',), reachable=True):
    return ProviderHealthSnapshot(
        account_id='ig-1', provider_account_ref='meta-123', username=username,
        token_state=token, permission_state=permission,
        granted_permissions=permissions, provider_reachable=reachable,
        observed_at=datetime(2026, 8, 16, 16, 0, tzinfo=timezone.utc).isoformat(),
        external_calls_made=0,
    )


def test_healthy_identity_is_verified_read_only(tmp_path: Path) -> None:
    registry = setup_registry(tmp_path)
    source = InMemoryMetaInstagramReadSource({'meta-123': health()})
    adapter = MetaInstagramReadHealthAdapter(tmp_path / 'health.sqlite3', registry, source)
    result = adapter.sync_and_verify('ig-1')
    assert result.state == 'verified-read-only'
    assert result.identity_match is True
    assert result.token_healthy is True
    assert result.permissions_healthy is True
    assert result.external_calls_made == 0
    assert adapter.snapshot()['publishing_enabled'] is False


def test_identity_mismatch_blocks(tmp_path: Path) -> None:
    registry = setup_registry(tmp_path)
    source = InMemoryMetaInstagramReadSource({'meta-123': health(username='wrong.handle')})
    result = MetaInstagramReadHealthAdapter(tmp_path / 'health.sqlite3', registry, source).sync_and_verify('ig-1')
    assert result.state == 'blocked'
    assert 'provider-identity-mismatch' in result.blockers


def test_unhealthy_token_and_missing_permission_block(tmp_path: Path) -> None:
    registry = setup_registry(tmp_path)
    source = InMemoryMetaInstagramReadSource({'meta-123': health(token='expired', permissions=())})
    result = MetaInstagramReadHealthAdapter(tmp_path / 'health.sqlite3', registry, source).sync_and_verify('ig-1')
    assert 'provider-token-unhealthy' in result.blockers
    assert 'required-read-permission-missing' in result.blockers
    assert result.state == 'blocked'


def test_missing_provider_reference_fails_closed_without_source_call(tmp_path: Path) -> None:
    registry = setup_registry(tmp_path, provider_ref=None)
    adapter = MetaInstagramReadHealthAdapter(tmp_path / 'health.sqlite3', registry, InMemoryMetaInstagramReadSource({}))
    result = adapter.sync_and_verify('ig-1')
    assert result.state == 'blocked'
    assert result.blockers == ('provider-account-ref-missing',)
    assert result.external_calls_made == 0


def test_verification_persists(tmp_path: Path) -> None:
    registry = setup_registry(tmp_path)
    source = InMemoryMetaInstagramReadSource({'meta-123': health()})
    db = tmp_path / 'health.sqlite3'
    adapter = MetaInstagramReadHealthAdapter(db, registry, source)
    adapter.sync_and_verify('ig-1')
    reopened = MetaInstagramReadHealthAdapter(db, registry, source)
    assert reopened.get_verification('ig-1').state == 'verified-read-only'


def test_c3_advances_exactly_to_c4() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.542'
    assert readiness['current_item'] == 'C3-meta-instagram-read-health-adapter'
    assert readiness['next_item'] == 'C4-draft-preview-approval-policy'
    assert readiness['instagram_publishing_enabled'] is False
    assert readiness['external_calls_made'] == 0
