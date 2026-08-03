from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.auron_demo1_telegram_certified_reclosure_assurance_v21_350 import (
    reset_telegram_certified_reclosure_assurance_store,
)

client = TestClient(app)


def setup_function() -> None:
    reset_telegram_certified_reclosure_assurance_store()


def test_v21_350_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.350/status' in paths
    assert '/auron/demo1/v21.350/assurance/start' in paths
    assert '/auron/demo1/v21.350/control/audit' in paths
    assert '/auron/demo1/v21.350/drift/open' in paths
    assert '/auron/demo1/v21.350/drift/resolve' in paths


def test_v21_350_empty_status_is_safe() -> None:
    response = client.get('/auron/demo1/v21.350/status')
    assert response.status_code == 200
    assert response.json()['assurance_records'] == 0
    assert response.json()['external_calls_made'] == 0


def test_v21_350_requires_explicit_start_phrase() -> None:
    response = client.post('/auron/demo1/v21.350/assurance/start', json={
        'actor': 'tester',
        'certification_id': 'missing',
        'start_phrase': 'wrong',
        'audit_interval_days': 90,
    })
    assert response.status_code == 403


def test_v21_350_missing_assurance_blocks_audit() -> None:
    response = client.post('/auron/demo1/v21.350/control/audit', json={
        'actor': 'tester',
        'assurance_id': 'missing',
        'audit_phrase': 'AUDIT AURON TELEGRAM CORRECTIVE CONTROL',
        'observed_evidence_hash': 'a' * 64,
        'control_state': 'healthy',
        'audit_statement': 'healthy',
    })
    assert response.status_code == 404
