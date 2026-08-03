from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.auron_demo1_telegram_expired_baseline_restoration_v21_353 import (
    reset_telegram_expired_baseline_restoration_store,
)

client = TestClient(app)


def setup_function() -> None:
    reset_telegram_expired_baseline_restoration_store()


def test_v21_353_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.353/status' in paths
    assert '/auron/demo1/v21.353/recertification/admit' in paths
    assert '/auron/demo1/v21.353/continuity/restore' in paths
    assert '/auron/demo1/v21.353/baseline/succeed' in paths


def test_v21_353_empty_status_is_safe() -> None:
    response = client.get('/auron/demo1/v21.353/status')
    assert response.status_code == 200
    body = response.json()
    assert body['recertification_admissions'] == 0
    assert body['continuity_restorations'] == 0
    assert body['successor_baselines'] == 0
    assert body['external_calls_made'] == 0


def test_v21_353_admission_requires_explicit_phrase() -> None:
    response = client.post('/auron/demo1/v21.353/recertification/admit', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'admission_phrase': 'wrong',
        'admission_reference': 'REF-1',
        'remediation_statement': 'Review expired baseline.',
    })
    assert response.status_code == 403


def test_v21_353_restoration_requires_admission() -> None:
    response = client.post('/auron/demo1/v21.353/continuity/restore', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'restoration_phrase': 'RESTORE AURON TELEGRAM ASSURANCE CONTINUITY',
        'observed_baseline_hash': 'a' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'RESTORE-1',
        'restoration_statement': 'Controls restored.',
    })
    assert response.status_code == 409
