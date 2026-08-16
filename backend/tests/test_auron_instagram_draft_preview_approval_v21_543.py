from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.content.auron_instagram_content_lifecycle_v21_541 import InstagramContentLifecycle
from app.content.auron_instagram_draft_preview_approval_v21_543 import (
    ContentApprovalError,
    InstagramDraftPreviewApprovalPolicy,
)
from app.content.auron_instagram_registry_calendar_v21_540 import (
    Brand,
    InstagramAccount,
    InstagramContentRegistryCalendar,
)
from app.content.auron_meta_instagram_read_health_v21_542 import (
    InMemoryMetaInstagramReadSource,
    MetaInstagramReadHealthAdapter,
    ProviderHealthSnapshot,
)
from app.core.auron_integration_readiness_v21_543 import get_integration_readiness


def stack(tmp_path: Path):
    registry = InstagramContentRegistryCalendar(tmp_path / 'registry.sqlite3')
    registry.upsert_brand(Brand('brand-1', 'AURON Media', 'Europe/Berlin', 'de'))
    registry.register_account(InstagramAccount('ig-1', 'brand-1', 'auron.media', 'meta-123', 'active'))
    registry.add_calendar_entry(content_id='c-1', brand_id='brand-1', account_id='ig-1', content_type='reel', title='Test Reel')

    lifecycle = InstagramContentLifecycle(tmp_path / 'lifecycle.sqlite3', registry)
    lifecycle.initialize('c-1', caption='Initial', hashtags=('AURON',), asset_uris=('file://reel.mp4',), actor='operator', reason='initial')
    lifecycle.transition('c-1', 'draft')
    lifecycle.transition('c-1', 'review')
    lifecycle.transition('c-1', 'approved')

    health = ProviderHealthSnapshot(
        account_id='ig-1', provider_account_ref='meta-123', username='auron.media',
        token_state='healthy', permission_state='healthy', granted_permissions=('account.read',),
        provider_reachable=True,
        observed_at=datetime(2026, 8, 16, 17, 0, tzinfo=timezone.utc).isoformat(),
        external_calls_made=0,
    )
    adapter = MetaInstagramReadHealthAdapter(
        tmp_path / 'provider.sqlite3', registry,
        InMemoryMetaInstagramReadSource({'meta-123': health}),
    )
    assert adapter.sync_and_verify('ig-1').state == 'verified-read-only'
    policy = InstagramDraftPreviewApprovalPolicy(tmp_path / 'approval.sqlite3', registry, lifecycle, adapter)
    return registry, lifecycle, adapter, policy


def test_preview_is_bound_to_exact_revision_and_idempotent(tmp_path: Path) -> None:
    _, lifecycle, _, policy = stack(tmp_path)
    preview = policy.generate_preview('c-1', actor='operator')
    again = policy.generate_preview('c-1', actor='other-actor')
    revision = lifecycle.get_revision('c-1', lifecycle.get('c-1').current_version)
    assert preview.preview_id == again.preview_id
    assert preview.revision_hash == revision.integrity_hash
    assert preview.external_calls_made == 0


def test_explicit_approval_allows_scheduler_only(tmp_path: Path) -> None:
    _, _, _, policy = stack(tmp_path)
    preview = policy.generate_preview('c-1', actor='operator')
    approval = policy.approve_for_publish('c-1', preview_id=preview.preview_id, approved_by='operator', reason='looks good')
    decision = policy.evaluate_publish_authorization('c-1')
    assert approval.state == 'approved-for-scheduler'
    assert decision.state == 'approved-for-scheduler'
    assert decision.approval_id == approval.approval_id
    assert decision.external_calls_made == 0
    assert policy.snapshot('c-1')['provider_write_available'] is False


def test_provider_read_verification_is_required_for_approval(tmp_path: Path) -> None:
    registry, lifecycle, adapter, _ = stack(tmp_path)
    broken = MetaInstagramReadHealthAdapter(
        tmp_path / 'broken-provider.sqlite3', registry,
        InMemoryMetaInstagramReadSource({}),
    )
    policy = InstagramDraftPreviewApprovalPolicy(tmp_path / 'broken-approval.sqlite3', registry, lifecycle, broken)
    preview = policy.generate_preview('c-1', actor='operator')
    with pytest.raises(ContentApprovalError, match='verified read-only'):
        policy.approve_for_publish('c-1', preview_id=preview.preview_id, approved_by='operator', reason='approve')


def test_new_revision_invalidates_old_preview_and_approval(tmp_path: Path) -> None:
    _, lifecycle, _, policy = stack(tmp_path)
    preview = policy.generate_preview('c-1', actor='operator')
    policy.approve_for_publish('c-1', preview_id=preview.preview_id, approved_by='operator', reason='approve v1')
    lifecycle.transition('c-1', 'draft')
    lifecycle.add_revision('c-1', caption='Changed caption', hashtags=('AURON', 'new'), actor='operator', reason='edit after review')
    lifecycle.transition('c-1', 'review')
    lifecycle.transition('c-1', 'approved')
    decision = policy.evaluate_publish_authorization('c-1')
    assert decision.state == 'blocked'
    assert 'publish-approval-stale-for-current-revision' in decision.blockers


def test_revocation_blocks_authorization(tmp_path: Path) -> None:
    _, _, _, policy = stack(tmp_path)
    preview = policy.generate_preview('c-1', actor='operator')
    approval = policy.approve_for_publish('c-1', preview_id=preview.preview_id, approved_by='operator', reason='approve')
    revoked = policy.revoke(approval.approval_id)
    assert revoked.state == 'revoked'
    decision = policy.evaluate_publish_authorization('c-1')
    assert decision.state == 'blocked'
    assert 'explicit-publish-approval-missing' in decision.blockers


def test_c4_advances_exactly_to_c5() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.543'
    assert readiness['current_item'] == 'C4-draft-preview-approval-policy'
    assert readiness['next_item'] == 'C5-scheduler-dry-run'
    assert readiness['instagram_publishing_enabled'] is False
    assert readiness['instagram_provider_write_available'] is False
    assert readiness['external_calls_made'] == 0
