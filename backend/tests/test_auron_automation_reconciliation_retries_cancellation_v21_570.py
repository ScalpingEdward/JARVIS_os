import json
from dataclasses import replace

from app.automation.auron_automation_reconciliation_retries_cancellation_v21_570 import (
    AutomationActionResult,
    AutomationReconciliationRetryCancellationService,
)
from app.core.auron_integration_readiness_v21_570 import get_integration_readiness


class FakeSimulation:
    def list_actions(self, plan_id):
        return (
            type('A', (), {'action_id':'a1','ordinal':1})(),
            type('A', (), {'action_id':'a2','ordinal':2})(),
        )


class FakeExecution:
    def __init__(self, decision):
        self.decision = decision
        self.simulation = FakeSimulation()
    def get_decision_by_plan(self, plan_id):
        return self.decision if self.decision.plan_id == plan_id else None


class Reader:
    def __init__(self, states): self.states = states
    def read_action_result(self, ref):
        action_id = 'a1' if ref == 'r1' else 'a2'
        ordinal = 1 if action_id == 'a1' else 2
        return AutomationActionResult(action_id, ref, self.states[ref], f'exec-1:{ordinal}', '2026-08-17T20:00:00+00:00', 1)


class Canceller:
    def cancel_action(self, *, provider_result_ref, idempotency_key): return 'cancelled'


def decision(state='submitted-for-reconciliation'):
    from app.automation.auron_automation_controlled_execution_v21_569 import AutomationExecutionDecision
    return AutomationExecutionDecision(
        'exec-1','plan-1','wf-1','op','appr','hash',state,(),json.dumps({'a1':'r1','a2':'r2'}),
        '2026-08-17T19:00:00+00:00',2,1,
    )


def test_all_actions_must_verify(tmp_path):
    service = AutomationReconciliationRetryCancellationService(
        tmp_path/'r.sqlite3',FakeExecution(decision()),Reader({'r1':'completed','r2':'succeeded'}))
    record = service.reconcile('plan-1')
    assert record.state == 'verified-complete'
    assert record.verified_actions == 2
    assert record.failed_actions == 0
    assert record.retry_eligible is False


def test_retryable_result_is_bounded(tmp_path):
    service = AutomationReconciliationRetryCancellationService(
        tmp_path/'r.sqlite3',FakeExecution(decision()),Reader({'r1':'pending','r2':'completed'}),max_attempts=2)
    first = service.reconcile('plan-1')
    assert first.state == 'retry-eligible'
    assert service.retry_authorization('exec-1').retry_eligible is True
    second = service.reconcile('plan-1')
    assert second.state == 'retry-exhausted'
    assert second.retry_eligible is False


def test_idempotency_mismatch_fails_closed(tmp_path):
    class BadReader(Reader):
        def read_action_result(self, ref):
            result = super().read_action_result(ref)
            return replace(result,idempotency_key='wrong')
    service = AutomationReconciliationRetryCancellationService(
        tmp_path/'r.sqlite3',FakeExecution(decision()),BadReader({'r1':'completed','r2':'completed'}))
    record = service.reconcile('plan-1')
    assert record.state == 'blocked'
    assert any(x.startswith('idempotency-key-mismatch:') for x in record.blockers)


def test_non_submitted_execution_cannot_reconcile(tmp_path):
    service = AutomationReconciliationRetryCancellationService(
        tmp_path/'r.sqlite3',FakeExecution(decision('execution-transport-disabled')),Reader({'r1':'completed','r2':'completed'}))
    record = service.reconcile('plan-1')
    assert record.state == 'blocked'
    assert 'submitted-d22-execution-required' in record.blockers


def test_cancellation_is_explicit_and_persisted(tmp_path):
    service = AutomationReconciliationRetryCancellationService(
        tmp_path/'r.sqlite3',FakeExecution(decision()),Reader({'r1':'pending','r2':'running'}),Canceller())
    service.reconcile('plan-1')
    record = service.request_cancellation('plan-1')
    assert record.cancellation_requested is True
    assert record.cancellation_state == 'cancelled'
    assert len(service.history('exec-1')) >= 2


def test_d23_readiness_advances_to_command_centre():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.570'
    assert readiness['next_item'] == 'D24-automation-command-centre-operations'
    assert readiness['automation_execution_enabled'] is False
    assert readiness['automation_cross_vertical_execution_enabled'] is False
