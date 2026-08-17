from app.research.auron_research_watch_reconciliation_v21_562 import (
    ResearchWatchReconciliationService,
    ResearchWatchRetryPolicy,
)
from app.research.auron_research_controlled_watch_v21_561 import ResearchWatchRun
from app.core.auron_integration_readiness_v21_562 import get_integration_readiness


class FakeRegistry:
    def __init__(self, freshness='fresh'):
        self.freshness = freshness
    def list_results(self, query_id):
        return (type('Result', (), {'source_id': 'source-1'})(),) if query_id else ()
    def evidence_state(self, source_id, now=None):
        return type('Freshness', (), {'freshness_state': self.freshness})()


class FakeWatches:
    def __init__(self, tmp_path, run, freshness='fresh'):
        self.run_record = run
        self.integration = type('Integration', (), {'registry': FakeRegistry(freshness)})()
        self.retried = []
    def get_run(self, run_id):
        return self.run_record if run_id == self.run_record.run_id else None
    def run(self, watch_id, provider, *, scheduled_for, started_at=None):
        self.retried.append((watch_id, scheduled_for, started_at))
        return ResearchWatchRun('retry-run', watch_id, scheduled_for, started_at, 'completed-no-results', 'q2', None, 1, 0)


def run(state='completed-report-simulated', query_id='q1'):
    return ResearchWatchRun('run-1','watch-1','2026-08-17T10:00:00+00:00','2026-08-17T10:00:01+00:00',state,query_id,'report-1',2,0)


def test_successful_run_reconciles_with_fresh_evidence(tmp_path):
    service = ResearchWatchReconciliationService(tmp_path/'r.sqlite3', FakeWatches(tmp_path,run()))
    record = service.reconcile('run-1',at='2026-08-17T10:05:00+00:00')
    assert record.state == 'reconciled'
    assert record.freshness_state == 'fresh'
    assert record.fresh_sources == 1
    assert record.terminal is True
    assert record.downstream_actions_made == 0


def test_stale_evidence_fails_closed(tmp_path):
    service = ResearchWatchReconciliationService(tmp_path/'r.sqlite3', FakeWatches(tmp_path,run(),freshness='stale'))
    record = service.reconcile('run-1',at='2026-08-17T13:00:00+00:00')
    assert record.state == 'freshness-failed-stale-evidence'
    assert record.stale_sources == 1
    assert record.terminal is True
    assert record.retry_due_at is None


def test_retryable_failure_gets_bounded_backoff(tmp_path):
    failed = run(state='failed:provider-timeout',query_id=None)
    service = ResearchWatchReconciliationService(
        tmp_path/'r.sqlite3', FakeWatches(tmp_path,failed),
        ResearchWatchRetryPolicy(max_attempts=3,base_delay_seconds=300,max_delay_seconds=1200),
    )
    record = service.reconcile('run-1',at='2026-08-17T10:05:00+00:00')
    assert record.state == 'retry-scheduled'
    assert record.retry_attempt == 1
    assert record.retry_due_at == '2026-08-17T10:10:00+00:00'
    assert record.terminal is False


def test_retry_only_runs_when_due_and_reenters_watch_boundary(tmp_path):
    failed = run(state='failed:provider-timeout',query_id=None)
    watches = FakeWatches(tmp_path,failed)
    service = ResearchWatchReconciliationService(tmp_path/'r.sqlite3',watches)
    service.reconcile('run-1',at='2026-08-17T10:05:00+00:00')
    assert service.retry_if_due('run-1',object(),at='2026-08-17T10:09:59+00:00') is None
    retried = service.retry_if_due('run-1',object(),at='2026-08-17T10:10:00+00:00')
    assert retried.run_id == 'retry-run'
    assert watches.retried[0][0] == 'watch-1'
    assert '#retry-1' in watches.retried[0][1]


def test_blocked_run_is_terminal_and_never_retried(tmp_path):
    blocked = run(state='blocked:watch-kill-switch-active',query_id=None)
    service = ResearchWatchReconciliationService(tmp_path/'r.sqlite3',FakeWatches(tmp_path,blocked))
    record = service.reconcile('run-1',at='2026-08-17T10:05:00+00:00')
    assert record.state == 'policy-blocked'
    assert record.terminal is True
    assert service.retry_if_due('run-1',object(),at='2026-08-17T11:00:00+00:00') is None


def test_reconciliation_is_idempotent(tmp_path):
    service = ResearchWatchReconciliationService(tmp_path/'r.sqlite3',FakeWatches(tmp_path,run()))
    first = service.reconcile('run-1',at='2026-08-17T10:05:00+00:00')
    second = service.reconcile('run-1',at='2026-08-17T11:05:00+00:00')
    assert first == second
    assert len(service.list_for_watch('watch-1')) == 1


def test_d15_readiness_advances_to_command_centre():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.562'
    assert readiness['next_item'] == 'D16-research-command-centre-operations'
    assert readiness['research_unattended_actions_enabled'] is False
    assert readiness['research_downstream_execution_enabled'] is False
