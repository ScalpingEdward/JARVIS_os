from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_alert_delivery_state_commit_v21_287 as commit
from app.api.routes import auron_demo1_alert_retry_result_verification_v21_286 as retry_result
from app.api.routes import auron_demo1_completion_alert_delivery_boundary_v21_281 as delivery
from app.main import app


def setup_function() -> None:
    delivery.reset_alert_delivery_store()
    retry_result.reset_retry_result_store()
    commit.reset_delivery_state_commit_store()


def _terminal_delivery(state: str = 'verified-delivered') -> str:
    delivery_id = 'delivery-287'
    delivery._delivery_store[delivery_id] = {
        'delivery_id': delivery_id,
        'delivery_state': 'prepared-not-dispatched',
        'acknowledged': False,
    }
    retry_result._retry_result_store['result-287'] = {
        'result_id': 'result-287',
        'retry_dispatch_id': 'retry-dispatch-287',
        'retry_id': 'retry-287',
        'dispatch_id': 'dispatch-287',
        'delivery_id': delivery_id,
        'attempt': 2,
        'provider_status': 'delivered' if state == 'verified-delivered' else 'temporary-failure',
        'provider_receipt_id': 'provider-287',
        'verified_at': '2026-08-02T09:50:00+00:00',
        'terminal': True,
        'delivery_state': state,
    }
    return delivery_id


def test_terminal_retry_result_commits_delivery_state() -> None:
    delivery_id = _terminal_delivery()
    result = commit.commit_delivery_state(
        delivery_id,
        commit.DeliveryStateCommitRequest(actor='brano'),
    )
    assert result['state'] == 'alert-delivery-state-committed'
    assert result['commit']['committed_delivery_state'] == 'verified-delivered'
    assert delivery._delivery_store[delivery_id]['delivery_state'] == 'verified-delivered'
    assert delivery._delivery_store[delivery_id]['terminal'] is True
    assert result['external_calls_made'] == 0
    assert result['terminal_execution_state_modified'] is False


def test_retry_exhausted_state_is_committed() -> None:
    delivery_id = _terminal_delivery('retry-exhausted')
    result = commit.commit_delivery_state(
        delivery_id,
        commit.DeliveryStateCommitRequest(actor='brano', note='budget exhausted'),
    )
    assert result['commit']['committed_delivery_state'] == 'retry-exhausted'
    assert result['commit']['note'] == 'budget exhausted'


def test_non_terminal_delivery_cannot_be_committed() -> None:
    delivery_id = 'delivery-open'
    delivery._delivery_store[delivery_id] = {
        'delivery_id': delivery_id,
        'delivery_state': 'prepared-not-dispatched',
        'acknowledged': False,
    }
    client = TestClient(app)
    response = client.post(
        f'/auron/demo1/v21.287/commit/{delivery_id}',
        json={'actor': 'brano'},
    )
    assert response.status_code == 409
    assert 'Terminal retry result required' in response.json()['detail']


def test_delivery_state_commit_is_idempotent() -> None:
    delivery_id = _terminal_delivery()
    payload = commit.DeliveryStateCommitRequest(actor='brano')
    first = commit.commit_delivery_state(delivery_id, payload)
    replay = commit.commit_delivery_state(delivery_id, payload)
    assert replay['state'] == 'alert-delivery-state-already-committed'
    assert replay['idempotent_replay'] is True
    assert replay['commit']['commit_id'] == first['commit']['commit_id']


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.287/command-center')
    assert response.status_code == 200
    assert 'v21.287' in response.text
    assert 'AURON ALERT DELIVERY STATE COMMIT COMMAND CENTER' in response.text
