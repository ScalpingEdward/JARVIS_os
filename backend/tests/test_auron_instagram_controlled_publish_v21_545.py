from datetime import datetime, timezone
from pathlib import Path

from app.core.auron_integration_readiness_v21_545 import get_integration_readiness
from app.content.auron_instagram_content_lifecycle_v21_541 import InstagramContentLifecycle
from app.content.auron_instagram_controlled_publish_v21_545 import ControlledInstagramPublishService
from app.content.auron_instagram_draft_preview_approval_v21_543 import InstagramDraftPreviewApprovalPolicy
from app.content.auron_instagram_registry_calendar_v21_540 import Brand, InstagramAccount, InstagramContentRegistryCalendar
from app.content.auron_instagram_scheduler_dry_run_v21_544 import InstagramSchedulerDryRun
from app.content.auron_meta_instagram_read_health_v21_542 import InMemoryMetaInstagramReadSource, MetaInstagramReadHealthAdapter, ProviderHealthSnapshot


def stack(tmp_path: Path):
    registry = InstagramContentRegistryCalendar(tmp_path/'registry.sqlite3')
    registry.upsert_brand(Brand('brand','Brand','Europe/Berlin','de'))
    registry.register_account(InstagramAccount('ig','brand','brand','provider-1','active'))
    registry.add_calendar_entry(content_id='c1',brand_id='brand',account_id='ig',content_type='reel',title='Reel')
    lifecycle = InstagramContentLifecycle(tmp_path/'lifecycle.sqlite3', registry)
    lifecycle.initialize('c1',caption='Hello',actor='operator',reason='initial')
    lifecycle.transition('c1','draft'); lifecycle.transition('c1','review'); lifecycle.transition('c1','approved')
    snapshot = ProviderHealthSnapshot('ig','provider-1','brand','healthy','healthy',('account.read',),True,datetime(2026,8,16,17,0,tzinfo=timezone.utc).isoformat(),0)
    health = MetaInstagramReadHealthAdapter(tmp_path/'health.sqlite3',registry,InMemoryMetaInstagramReadSource({'provider-1':snapshot}))
    assert health.sync_and_verify('ig').state == 'verified-read-only'
    approvals = InstagramDraftPreviewApprovalPolicy(tmp_path/'approval.sqlite3',registry,lifecycle,health)
    preview = approvals.generate_preview('c1',actor='operator')
    approvals.approve_for_publish('c1',preview_id=preview.preview_id,approved_by='operator',reason='approved')
    lifecycle.transition('c1','scheduled',scheduled_for='2026-08-17T12:00:00+00:00')
    scheduler = InstagramSchedulerDryRun(tmp_path/'scheduler.sqlite3',registry,lifecycle,approvals)
    plan = scheduler.schedule('c1')
    plan = scheduler.simulate(plan.plan_id,at=datetime(2026,8,17,12,1,tzinfo=timezone.utc))
    publish = ControlledInstagramPublishService(tmp_path/'publish.sqlite3',lifecycle,approvals,scheduler)
    return publish, plan


def test_missing_scope_fails_closed(tmp_path):
    publish, plan = stack(tmp_path)
    decision = publish.evaluate(plan.plan_id)
    assert decision.state == 'blocked'
    assert 'publish-scope-missing' in decision.blockers
    assert decision.external_calls_made == 0


def test_scope_requires_operator_and_clear_kill_switch(tmp_path):
    publish, plan = stack(tmp_path)
    publish.configure_scope('ig',enabled=True,operator_approved=False,kill_switch=True)
    decision = publish.evaluate(plan.plan_id)
    assert decision.state == 'blocked'
    assert 'operator-approval-required' in decision.blockers
    assert 'publish-kill-switch-active' in decision.blockers


def test_ready_scope_reaches_controlled_boundary_but_default_writer_is_disabled(tmp_path):
    publish, plan = stack(tmp_path)
    publish.configure_scope('ig',enabled=True,operator_approved=True,kill_switch=False)
    decision = publish.evaluate(plan.plan_id)
    assert decision.state == 'ready-for-controlled-publish'
    result = publish.execute(plan.plan_id)
    assert result.state == 'provider-write-disabled'
    assert result.external_calls_made == 0


def test_publish_decision_is_idempotent(tmp_path):
    publish, plan = stack(tmp_path)
    first = publish.evaluate(plan.plan_id)
    second = publish.evaluate(plan.plan_id)
    assert first.publish_id == second.publish_id
    assert first == second


def test_c6_readiness_keeps_real_publishing_disabled():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.545'
    assert readiness['next_item'] == 'C7-publish-reconciliation-retries'
    assert readiness['instagram_publishing_enabled'] is False
    assert readiness['instagram_provider_write_available'] is False
    assert readiness['external_calls_made'] == 0
