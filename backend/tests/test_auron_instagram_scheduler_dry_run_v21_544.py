from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.auron_integration_readiness_v21_544 import get_integration_readiness
from app.content.auron_instagram_content_lifecycle_v21_541 import InstagramContentLifecycle
from app.content.auron_instagram_draft_preview_approval_v21_543 import InstagramDraftPreviewApprovalPolicy
from app.content.auron_instagram_registry_calendar_v21_540 import Brand, InstagramAccount, InstagramContentRegistryCalendar
from app.content.auron_instagram_scheduler_dry_run_v21_544 import ContentSchedulerError, InstagramSchedulerDryRun
from app.content.auron_meta_instagram_read_health_v21_542 import InMemoryMetaInstagramReadSource, MetaInstagramAccountHealth, MetaInstagramReadHealthAdapter


def stack(tmp_path: Path):
    registry = InstagramContentRegistryCalendar(tmp_path/'registry.sqlite3')
    registry.upsert_brand(Brand('brand','Brand','Europe/Berlin','de'))
    registry.register_account(InstagramAccount('ig','brand','brand','provider-1','active'))
    registry.add_calendar_entry(content_id='c1',brand_id='brand',account_id='ig',content_type='reel',title='Reel')
    lifecycle = InstagramContentLifecycle(tmp_path/'lifecycle.sqlite3', registry)
    lifecycle.initialize('c1',caption='Hello',actor='operator',reason='initial')
    lifecycle.transition('c1','draft'); lifecycle.transition('c1','review'); lifecycle.transition('c1','approved')
    health = MetaInstagramReadHealthAdapter(tmp_path/'health.sqlite3',registry,InMemoryMetaInstagramReadSource({
        'ig': MetaInstagramAccountHealth('ig','provider-1','brand',True,True,True,('instagram_basic',),())
    }))
    health.verify_account('ig')
    approvals = InstagramDraftPreviewApprovalPolicy(tmp_path/'approval.sqlite3',registry,lifecycle,health)
    preview = approvals.generate_preview('c1',actor='operator')
    approvals.approve_for_publish('c1',preview_id=preview.preview_id,approved_by='operator',reason='approved')
    scheduled_for='2026-08-17T12:00:00+00:00'
    lifecycle.transition('c1','scheduled',scheduled_for=scheduled_for)
    scheduler=InstagramSchedulerDryRun(tmp_path/'scheduler.sqlite3',registry,lifecycle,approvals)
    return lifecycle,approvals,scheduler


def test_schedule_is_deterministic_and_idempotent(tmp_path):
    _,_,scheduler=stack(tmp_path)
    first=scheduler.schedule('c1'); second=scheduler.schedule('c1')
    assert first.plan_id==second.plan_id
    assert first.payload_hash==second.payload_hash
    assert first.state=='scheduled-dry-run'
    assert first.external_calls_made==0


def test_due_queue_and_simulation_make_no_external_calls(tmp_path):
    _,_,scheduler=stack(tmp_path)
    plan=scheduler.schedule('c1')
    due=scheduler.due(datetime(2026,8,17,12,1,tzinfo=timezone.utc))
    assert [x.plan_id for x in due]==[plan.plan_id]
    result=scheduler.simulate(plan.plan_id,at=datetime(2026,8,17,12,1,tzinfo=timezone.utc))
    assert result.state=='simulated-success'
    assert result.external_calls_made==0


def test_not_due_cannot_simulate(tmp_path):
    _,_,scheduler=stack(tmp_path)
    plan=scheduler.schedule('c1')
    with pytest.raises(ContentSchedulerError):
        scheduler.simulate(plan.plan_id,at=datetime(2026,8,17,11,59,tzinfo=timezone.utc))


def test_revoked_approval_blocks_due_plan(tmp_path):
    _,approvals,scheduler=stack(tmp_path)
    plan=scheduler.schedule('c1')
    approvals.revoke(plan.approval_id)
    result=scheduler.simulate(plan.plan_id,at=datetime(2026,8,17,12,1,tzinfo=timezone.utc))
    assert result.state=='blocked-authorization-changed'


def test_c5_readiness_keeps_provider_write_disabled():
    readiness=get_integration_readiness()
    assert readiness['roadmap_version']=='v21.544'
    assert readiness['next_item']=='C6-controlled-meta-publish-boundary'
    assert readiness['instagram_publishing_enabled'] is False
    assert readiness['instagram_provider_write_available'] is False
    assert readiness['external_calls_made']==0
