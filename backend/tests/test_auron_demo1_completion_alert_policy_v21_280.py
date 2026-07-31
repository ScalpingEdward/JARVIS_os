from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_completion_alert_policy_v21_280 import _evaluate
from app.main import app


def test_alert_policy_is_ok_when_all_entries_are_verified() -> None:
    result = _evaluate([
        {'integrity_verified': True},
        {'integrity_verified': True},
    ])

    assert result['severity'] == 'ok'
    assert result['signal_active'] is False
    assert result['health']['health_percent'] == 100.0
    assert result['operator_action'] == 'none'


def test_alert_policy_warns_on_single_integrity_failure() -> None:
    result = _evaluate([
        {'integrity_verified': True},
        {'integrity_verified': False},
    ])

    assert result['severity'] == 'warning'
    assert result['signal_active'] is True
    assert 'failure_count_at_or_above_warning_threshold' in result['reasons']
    assert result['operator_action'] == 'review-integrity-health'


def test_alert_policy_becomes_critical_at_failure_threshold() -> None:
    result = _evaluate([
        {'integrity_verified': False},
        {'integrity_verified': False},
        {'integrity_verified': False},
        {'integrity_verified': True},
    ])

    assert result['severity'] == 'critical'
    assert result['signal_active'] is True
    assert 'failure_count_at_or_above_critical_threshold' in result['reasons']
    assert result['operator_action'] == 'investigate-integrity-failures'


def test_policy_endpoint_is_read_only() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.280/policy')

    assert response.status_code == 200
    body = response.json()
    assert body['read_only'] is True
    assert body['external_calls_made'] == 0
    assert body['business_mutations_made'] == 0


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.280/command-center')

    assert response.status_code == 200
    assert 'v21.280' in response.text
    assert 'AURON COMPLETION ALERT POLICY COMMAND CENTER' in response.text
