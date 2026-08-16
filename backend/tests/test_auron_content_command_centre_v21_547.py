from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.content.auron_content_command_centre_v21_547 import ContentCommandCentreService
from app.content.auron_instagram_content_lifecycle_v21_541 import InstagramContentLifecycle
from app.content.auron_instagram_controlled_publish_v21_545 import ControlledInstagramPublishService
from app.content.auron_instagram_draft_preview_approval_v21_543 import InstagramDraftPreviewApprovalPolicy
from app.content.auron_instagram_publish_reconciliation_v21_546 import InstagramPublishReconciliationService
from app.content.auron_instagram_registry_calendar_v21_540 import Brand, InstagramAccount, InstagramContentRegistryCalendar
from app.content.auron_instagram_scheduler_dry_run_v21_544 import InstagramSchedulerDryRun
from app.content.auron_meta_instagram_read_health_v21_542 import InMemoryMetaInstagramReadSource, MetaInstagramReadHealthAdapter, ProviderHealthSnapshot
from app.core.auron_integration_readiness_v21_547 import get_integration_readiness


def stack(tmp_path: Path):
    registry = InstagramContentRegistryCalendar(tmp_path / 'registry.sqlite3')
    registry.upsert_brand(Brand('brand', 'Brand', 'Europe/Berlin', 'de'))
    registry.register_account(InstagramAccount('ig', 'brand', 'brand', 'provider-1', 'active'))
    registry.add_calendar_entry(content_id='c1', brand_id='brand', account_id='ig', content_type='reel', title='Reel')
    lifecycle = InstagramContentLifecycle(tmp_path / 'lifecycle.sqlite3', registry)
    lifecycle.initialize('c1', caption='Hello', actor='operator', reason='initial')
    lifecycle.transition('c1', 'draft'); lifecycle.transition('c1', 'review'); lifecycle.transition('c1', 'approved')
    provider = ProviderHealthSnapshot('ig', 'provider-1', 'brand', 'healthy', 'healthy', ('account.read',), True,
                                      datetime(2026, 8, 16, 17, 0, tzinfo=timezone.utc).isoformat(), 0)
    health = MetaInstagramReadHealthAdapter(tmp_path / 'health.sqlite3', registry,
                                            InMemoryMetaInstagramReadSource({'provider-1': provider}))
    assert health.sync_and_verify('ig').state == 'verified-read-only'
    approvals = InstagramDraftPreviewApprovalPolicy(tmp_path / 'approval.sqlite3', registry, lifecycle, health)
    preview = approvals.generate_preview('c1', actor='operator')
    approvals.approve_for_publish('c1', preview_id=preview.preview_id, approved_by='operator', reason='approved')
    lifecycle.transition('c1', 'scheduled', scheduled_for='2026-08-17T12:00:00+00:00')
    scheduler = InstagramSchedulerDryRun(tmp_path / 'scheduler.sqlite3', registry, lifecycle, approvals)
    publish = ControlledInstagramPublishService(tmp_path / 'publish.sqlite3', lifecycle, approvals, scheduler)
    reconciliation = InstagramPublishReconciliationService(tmp_path / 'recon.sqlite3', publish)
    service = ContentCommandCentreService(tmp_path / 'command.sqlite3', registry, lifecycle, approvals,
                                          scheduler, publish, reconciliation)
    return service


def test_snapshot_preserves_command_field_and_provider_safety(tmp_path):
    service = stack(tmp_path)
    snapshot = service.snapshot()
    assert snapshot['command_input_available'] is True
    assert snapshot['provider_write_enabled_by_default'] is False
    assert snapshot['recurring_automation_bypasses_approval'] is False
    assert snapshot['external_calls_made'] == 0
    assert len(snapshot['accounts']) == 1


def test_recurring_automation_defaults_fail_closed(tmp_path):
    service = stack(tmp_path)
    policy = service.configure_automation('auto-1', 'ig', cadence='RRULE:FREQ=DAILY')
    assert policy.enabled is False
    assert policy.operator_approved is False
    assert policy.action == 'prepare-and-schedule'


def test_recurring_automation_can_be_explicitly_authorized_without_publish_bypass(tmp_path):
    service = stack(tmp_path)
    policy = service.configure_automation('auto-1', 'ig', cadence='RRULE:FREQ=DAILY',
                                          enabled=True, operator_approved=True)
    assert policy.enabled is True
    assert policy.operator_approved is True
    snapshot = service.snapshot()
    assert snapshot['recurring_automation_bypasses_approval'] is False
    assert snapshot['provider_write_enabled_by_default'] is False


def test_direct_publish_automation_action_is_rejected(tmp_path):
    service = stack(tmp_path)
    with pytest.raises(ValueError, match='direct provider publishing'):
        service.configure_automation('auto-1', 'ig', cadence='RRULE:FREQ=DAILY', action='publish-directly')


def test_account_view_exposes_content_and_alerts(tmp_path):
    service = stack(tmp_path)
    view = service.account_view('ig')
    assert view['account']['account_id'] == 'ig'
    assert len(view['content']) == 1
    assert 'publish-scope-missing' in view['alerts']
    assert view['external_calls_made'] == 0


def test_c8_completes_content_phase_without_enabling_provider_write():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.547'
    assert readiness['current_item'] == 'C8-content-command-centre-recurring-automation'
    assert readiness['instagram_content_phase_complete'] is True
    assert readiness['next_item'] == 'D1-additional-vertical-selection-and-adapter-onboarding'
    assert readiness['instagram_publishing_enabled'] is False
    assert readiness['instagram_provider_write_available'] is False
    assert readiness['external_calls_made'] == 0
