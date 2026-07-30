from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.phoenix_demo1_approval_inbox_v21_228 import ApprovalInboxCreate, DeferredRecoveryRequest
from app.services.phoenix_demo1_approval_inbox_v21_228 import PersistentApprovalInbox, approval_inbox_service
from app.schemas.phoenix_demo1_v21_225 import DemoRequest
from app.services.phoenix_demo1_v21_225 import run_demo_vertical_slice

NOW = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)


def record(state='deferred'):
    return ApprovalInboxCreate(
        approval_id='approval-demo-001', session_id='s1', workspace_id='w1', operator_id='o1',
        command='perform gated action', reason='approval required', priority='normal', action_risk='high',
        state=state, created_at=NOW, deferred_until=NOW + timedelta(minutes=5),
    )


def test_inbox_survives_service_restart(tmp_path):
    path = tmp_path / 'inbox.json'
    first = PersistentApprovalInbox(str(path))
    first.upsert(record(state='pending'))
    second = PersistentApprovalInbox(str(path))
    assert second.status().persistent is True
    assert second.status().pending == 1
    assert second.list()[0].approval_id == 'approval-demo-001'


def test_deferred_request_recovers_to_pending_without_execution(tmp_path):
    inbox = PersistentApprovalInbox(str(tmp_path / 'inbox.json'))
    inbox.upsert(record())
    result = inbox.recover_deferred(DeferredRecoveryRequest(now=NOW + timedelta(minutes=6)))
    assert len(result.recovered) == 1
    assert result.recovered[0].state == 'pending'
    assert result.autonomous_execution_performed is False


def test_quiet_window_keeps_request_deferred(tmp_path):
    inbox = PersistentApprovalInbox(str(tmp_path / 'inbox.json'))
    inbox.upsert(record())
    result = inbox.recover_deferred(DeferredRecoveryRequest(now=NOW + timedelta(minutes=2)))
    assert not result.recovered
    assert len(result.still_deferred) == 1


def test_risk_brain_blocks_recovery(tmp_path):
    inbox = PersistentApprovalInbox(str(tmp_path / 'inbox.json'))
    inbox.upsert(record())
    result = inbox.recover_deferred(DeferredRecoveryRequest(now=NOW + timedelta(minutes=6), risk_brain_hard_block=True))
    assert len(result.blocked) == 1
    assert result.blocked[0].state == 'blocked'


def test_demo1_gated_request_is_written_to_durable_inbox():
    approval_inbox_service.reset_for_tests()
    req = DemoRequest(
        session_id='integration-228', workspace_id='ws-1', operator_id='operator-1',
        command='perform gated action', action_risk='high', now=NOW,
        voice_available=True, text_available=True,
    )
    response = run_demo_vertical_slice(req)
    assert response.state == 'queued-for-approval'
    assert approval_inbox_service.status().pending == 1
    approval_inbox_service.reset_for_tests()


def test_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.228/approvals/status' in paths
    assert '/phoenix/demo1/v21.228/approvals' in paths
    assert '/phoenix/demo1/v21.228/approvals/recover-deferred' in paths


def test_status_endpoint_declares_persistence():
    approval_inbox_service.reset_for_tests()
    response = TestClient(app).get('/phoenix/demo1/v21.228/approvals/status')
    assert response.status_code == 200
    assert response.json()['persistent'] is True
    assert response.json()['autonomous_high_risk_execution_enabled'] is False
