from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_expired_renewed_successor_restoration_v21_358 import (
    reset_telegram_expired_renewed_successor_restoration_store,
    router,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def setup_function() -> None:
    reset_telegram_expired_renewed_successor_restoration_store()


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.358/status' in paths
    assert '/auron/demo1/v21.358/recertification/admit' in paths
    assert '/auron/demo1/v21.358/continuity/restore' in paths
    assert '/auron/demo1/v21.358/baseline/succeed' in paths


def test_safe_empty_status() -> None:
    response = client.get('/auron/demo1/v21.358/status')
    assert response.status_code == 200
    body = response.json()
    assert body['recertification_admissions'] == 0
    assert body['continuity_restorations'] == 0
    assert body['next_successor_baselines'] == 0
    assert body['external_calls_made'] == 0


def test_explicit_admission_phrase_enforced() -> None:
    response = client.post('/auron/demo1/v21.358/recertification/admit', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'admission_phrase': 'WRONG',
        'admission_reference': 'ref',
        'remediation_statement': 'statement',
    })
    assert response.status_code == 403


def test_admission_required_before_restoration() -> None:
    response = client.post('/auron/demo1/v21.358/continuity/restore', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'restoration_phrase': 'RESTORE AURON TELEGRAM RENEWED SUCCESSOR CONTINUITY',
        'observed_expired_baseline_hash': 'a' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'ref',
        'restoration_statement': 'statement',
    })
    assert response.status_code == 409
