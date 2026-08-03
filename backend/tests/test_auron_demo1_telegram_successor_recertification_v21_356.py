from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_recertification_v21_356 import (
    reset_telegram_successor_recertification_store,
    router,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_recertification_store()


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.356/status' in paths
    assert '/auron/demo1/v21.356/drift-remediation/validate' in paths
    assert '/auron/demo1/v21.356/succession/recertify' in paths
    assert '/auron/demo1/v21.356/baseline/renew' in paths


def test_safe_empty_status() -> None:
    response = client.get('/auron/demo1/v21.356/status')
    assert response.status_code == 200
    body = response.json()
    assert body['drift_remediation_validations'] == 0
    assert body['succession_recertifications'] == 0
    assert body['renewed_successor_baselines'] == 0
    assert body['external_calls_made'] == 0


def test_explicit_validation_phrase_enforced() -> None:
    response = client.post('/auron/demo1/v21.356/drift-remediation/validate', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'validation_phrase': 'WRONG',
        'validation_reference': 'test',
        'validation_statement': 'test',
        'observed_successor_hash': 'a' * 64,
        'continuity_state': 'healthy',
    })
    assert response.status_code == 403


def test_missing_validation_blocks_recertification() -> None:
    response = client.post('/auron/demo1/v21.356/succession/recertify', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'recertification_phrase': 'RECERTIFY AURON TELEGRAM SUCCESSOR SUCCESSION',
        'recertification_reference': 'test',
        'recertification_statement': 'test',
    })
    assert response.status_code == 409
