from dataclasses import replace

from app.communications.auron_communications_reconciliation_retries_v21_554 import (
    CommunicationsReconciliationRetryService, ProviderMessageResult,
)
from app.core.auron_integration_readiness_v21_554 import get_integration_readiness


class FakeExecution:
    def __init__(self, decision): self.decision = decision
    def get_decision_by_plan(self, plan_id): return self.decision if self.decision.plan_id == plan_id else None


class Reader:
    def __init__(self, result): self.result = result
    def read_result(self, provider_message_ref): return self.result


class FailingReader:
    def read_result(self, provider_message_ref): raise RuntimeError('temporary provider failure')


def decision():
    from app.communications.auron_communications_controlled_execution_v21_553 import CommunicationsExecutionDecision
    return CommunicationsExecutionDecision(
        'exec-1','plan-1','intent-1','ch-1','approval-1','hash','provider-submitted',(),
        'provider-msg-1','2026-08-17T00:00:00+00:00',1,
    )


def result(state='delivered', **changes):
    base = ProviderMessageResult('provider-msg-1','ch-1',state,'exec-1','2026-08-17T00:01:00+00:00',1)
    return replace(base, **changes)


def test_verified_delivery_requires_matching_provider_evidence(tmp_path):
    service = CommunicationsReconciliationRetryService(tmp_path/'r.sqlite3', FakeExecution(decision()), Reader(result()))
    record = service.reconcile('plan-1')
    assert record.state == 'verified-delivered'
    assert record.retry_eligible is False
    assert record.external_calls_made == 1


def test_provider_identity_mismatch_fails_closed(tmp_path):
    service = CommunicationsReconciliationRetryService(
        tmp_path/'r.sqlite3', FakeExecution(decision()), Reader(result(channel_id='wrong', idempotency_key='wrong'))
    )
    record = service.reconcile('plan-1')
    assert record.state == 'blocked'
    assert 'provider-channel-mismatch' in record.blockers
    assert 'provider-idempotency-key-mismatch' in record.blockers


def test_pending_result_is_bounded_and_never_blindly_resent(tmp_path):
    service = CommunicationsReconciliationRetryService(tmp_path/'r.sqlite3', FakeExecution(decision()), Reader(result('pending')), max_attempts=2)
    first = service.reconcile('plan-1')
    assert first.state == 'retry-eligible'
    assert service.retry_authorization('exec-1').retry_eligible is True
    second = service.reconcile('plan-1')
    assert second.state == 'retry-exhausted'
    assert second.retry_eligible is False


def test_provider_read_errors_are_retryable_only_within_limit(tmp_path):
    service = CommunicationsReconciliationRetryService(tmp_path/'r.sqlite3', FakeExecution(decision()), FailingReader(), max_attempts=2)
    assert service.reconcile('plan-1').state == 'retry-eligible'
    second = service.reconcile('plan-1')
    assert second.state == 'blocked'
    assert second.retry_eligible is False


def test_non_submitted_execution_cannot_reconcile(tmp_path):
    d = replace(decision(), state='provider-write-disabled', provider_message_ref=None)
    service = CommunicationsReconciliationRetryService(tmp_path/'r.sqlite3', FakeExecution(d), Reader(result()))
    record = service.reconcile('plan-1')
    assert record.state == 'blocked'
    assert 'provider-submission-required' in record.blockers
    assert record.external_calls_made == 0


def test_reconciliation_history_is_append_only(tmp_path):
    service = CommunicationsReconciliationRetryService(tmp_path/'r.sqlite3', FakeExecution(decision()), Reader(result('pending')), max_attempts=3)
    service.reconcile('plan-1'); service.reconcile('plan-1')
    history = service.history('exec-1')
    assert len(history) == 2
    assert history[0]['attempt_count'] == 1
    assert history[1]['attempt_count'] == 2


def test_d7_readiness_advances_to_command_centre():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.554'
    assert readiness['next_item'] == 'D8-communications-command-centre-operations'
    assert readiness['communications_outbound_enabled'] is False
