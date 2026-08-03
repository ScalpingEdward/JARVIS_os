from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_expired_renewed_next_successor_restoration_v21_363 import (
    reset_telegram_expired_renewed_next_successor_restoration_store,
    router,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def setup_function() -> None:
    reset_telegram_expired_renewed_next_successor_restoration_store()


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.363/status' in paths
    assert '/auron/demo1/v21.363/recertification/admit' in paths
    assert '/auron/demo1/v21.363/continuity/restore' in paths
    assert '/auron/demo1/v21.363/baseline/succeed' in paths


def test_safe_empty_status() -> None:
    response = client.get('/auron/demo1/v21.363/status')
    assert response.status_code == 200
    body = response.json()
    assert body['recertification_admissions'] == 0
    assert body['continuity_restorations'] == 0
    assert body['successor_next_baselines'] == 0
    assert body['external_calls_made'] == 0


def test_explicit_admission_phrase_enforced() -> None:
    response = client.post('/auron/demo1/v21.363/recertification/admit', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'admission_phrase': 'WRONG',
        'admission_reference': 'ref',
        'remediation_statement': 'remediated',
    })
    assert response.status_code == 403


def test_admission_required_before_restoration() -> None:
    response = client.post('/auron/demo1/v21.363/continuity/restore', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'restoration_phrase': 'RESTORE AURON TELEGRAM RENEWED NEXT SUCCESSOR CONTINUITY',
        'observed_expired_baseline_hash': 'a' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'ref',
        'restoration_statement': 'restored',
    })
    assert response.status_code == 409


def test_restoration_required_before_succession() -> None:
    response = client.post('/auron/demo1/v21.363/baseline/succeed', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'succession_phrase': 'ESTABLISH AURON TELEGRAM SUCCESSOR NEXT BASELINE',
        'successor_reference': 'ref',
        'successor_next_hash': 'b' * 64,
        'validity_days': 365,
        'health_interval_days': 30,
    })
    assert response.status_code == 409
