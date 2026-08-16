from datetime import datetime, timezone
from pathlib import Path

from app.core.auron_integration_readiness_v21_546 import get_integration_readiness
from app.content.auron_instagram_content_lifecycle_v21_541 import InstagramContentLifecycle
from app.content.auron_instagram_controlled_publish_v21_545 import ControlledInstagramPublishService, InstagramProviderWriteBoundary
from app.content.auron_instagram_draft_preview_approval_v21_543 import InstagramDraftPreviewApprovalPolicy
from app.content.auron_instagram_publish_reconciliation_v21_546 import (
    InstagramPublishReconciliationService,
    InstagramProviderResultBoundary,
    ProviderPublishStatus,
)
from app.content.auron_instagram_registry_calendar_v21_540 import Brand, InstagramAccount, InstagramContentRegistryCalendar
from app.content.auron_instagram_scheduler_dry_run_v21_544 import InstagramSchedulerDryRun
from app.content.auron_meta_instagram_read_health_v21_542 import InMemoryMetaInstagramReadSource, MetaInstagramReadHealthAdapter, ProviderHealthSnapshot


class FakeWriter(InstagramProviderWriteBoundary):
    def publish(self, **kwargs) -> str:
        return 'media-123'


class FakeResultReader(InstagramProviderResultBoundary):
    def __init__(self, status: ProviderPublishStatus) -> None:
        self.status = status

    def read_publish_status(self, provider_media_id: str) -> ProviderPublishStatus:
        return self.status


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
    scheduler.simulate(plan.plan_id,at=datetime(2026,8,17,12,1,tzinfo=timezone.utc))
    publish = ControlledInstagramPublishService(tmp_path/'publish.sqlite3',lifecycle,approvals,scheduler,writer=FakeWriter())
    publish.configure_scope('ig',enabled=True,operator_approved=True,kill_switch=False)
    decision = publish.execute(plan.plan_id)
    assert decision.state == 'provider-submitted'
    return publish, decision


def test_provider_published_result_reconciles(tmp_path):
    publish, decision = stack(tmp_path)
    status = ProviderPublishStatus('media-123','published','c1','ig',datetime.now(timezone.utc).isoformat(),False,1)
    service = InstagramPublishReconciliationService(tmp_path/'recon.sqlite3',publish,FakeResultReader(status))
    record = service.reconcile_decision(decision)
    assert record.state == 'matched-published'
    assert record.blockers == ()
    assert record.external_calls_made == 1
    assert service.require_reconciled_published(decision.publish_id).state == 'matched-published'


def test_mismatch_is_fail_closed(tmp_path):
    publish, decision = stack(tmp_path)
    status = ProviderPublishStatus('media-123','published','different-content','ig',datetime.now(timezone.utc).isoformat(),False,1)
    service = InstagramPublishReconciliationService(tmp_path/'recon.sqlite3',publish,FakeResultReader(status))
    record = service.reconcile_decision(decision)
    assert record.state == 'mismatched'
    assert 'provider-content-mismatch' in record.blockers
    assert record.next_retry_allowed is False


def test_retryable_provider_failure_is_bounded(tmp_path):
    publish, decision = stack(tmp_path)
    status = ProviderPublishStatus('media-123','failed','c1','ig',datetime.now(timezone.utc).isoformat(),True,1)
    service = InstagramPublishReconciliationService(tmp_path/'recon.sqlite3',publish,FakeResultReader(status),max_retry_attempts=2)
    first = service.reconcile_decision(decision)
    second = service.reconcile_decision(decision)
    third = service.reconcile_decision(decision)
    assert first.state == 'retry-eligible' and first.next_retry_allowed is True
    assert second.state == 'retry-eligible' and second.next_retry_allowed is True
    assert third.state == 'failed-provider-result' and third.next_retry_allowed is False
    assert len(service.events(decision.publish_id)) == 3


def test_disabled_result_boundary_never_invents_success(tmp_path):
    publish, decision = stack(tmp_path)
    service = InstagramPublishReconciliationService(tmp_path/'recon.sqlite3',publish)
    record = service.reconcile_decision(decision)
    assert record.state == 'provider-result-unavailable'
    assert 'provider-result-boundary-disabled' in record.blockers
    assert record.external_calls_made == 0


def test_c7_advances_exactly_to_c8():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.546'
    assert readiness['current_item'] == 'C7-publish-reconciliation-retries'
    assert readiness['next_item'] == 'C8-content-command-centre-recurring-automation'
    assert readiness['instagram_publishing_enabled'] is False
    assert readiness['external_calls_made'] == 0
