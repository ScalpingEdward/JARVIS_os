from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.auron_demo1_telegram_closed_record_remediation_reclosure_v21_348 import (
    reset_telegram_closed_record_remediation_reclosure_store,
)

client = TestClient(app)


def setup_function() -> None:
    reset_telegram_closed_record_remediation_reclosure_store()


def test_v21_348_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.348/status' in paths
    assert '/auron/demo1/v21.348/remediation/plan' in paths
    assert '/auron/demo1/v21.348/evidence/supersede' in paths
    assert '/auron/demo1/v21.348/lifecycle/reclose' in paths


def test_empty_status_is_safe() -> None:
    response = client.get('/auron/demo1/v21.348/status')
    assert response.status_code == 200
    assert response.json()['external_calls_made'] == 0
    assert response.json()['governed_reclosures'] == 0


def test_remediation_requires_explicit_phrase() -> None:
    response = client.post('/auron/demo1/v21.348/remediation/plan', json={
        'actor': 'tester',
        'record_id': 'missing-record',
        'plan_phrase': 'wrong',
        'root_cause': 'drift',
        'corrective_action': 'replace evidence',
        'validation_criteria': 'hash verified',
    })
    assert response.status_code == 403


def test_reclosure_requires_completed_chain() -> None:
    response = client.post('/auron/demo1/v21.348/lifecycle/reclose', json={
        'actor': 'tester',
        'record_id': 'missing-record',
        'reclosure_phrase': 'RECLOSE AURON TELEGRAM DISCLOSURE LIFECYCLE',
        'reclosure_reference': 'R-1',
        'residual_risk': 'low',
        'decision_statement': 'controls validated',
    })
    assert response.status_code == 409
