from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_next_successor_recertification_v21_361 import (
    reset_telegram_next_successor_recertification_store,
    router,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def setup_function() -> None:
    reset_telegram_next_successor_recertification_store()


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.361/status' in paths
    assert '/auron/demo1/v21.361/drift-remediation/validate' in paths
    assert '/auron/demo1/v21.361/succession/recertify' in paths
    assert '/auron/demo1/v21.361/baseline/renew' in paths


def test_safe_empty_status() -> None:
    response = client.get('/auron/demo1/v21.361/status')
    assert response.status_code == 200
    body = response.json()
    assert body['drift_remediation_validations'] == 0
    assert body['succession_recertifications'] == 0
    assert body['renewed_next_successor_baselines'] == 0
    assert body['external_calls_made'] == 0


def test_explicit_validation_phrase_enforced() -> None:
    response = client.post('/auron/demo1/v21.361/drift-remediation/validate', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'validation_phrase': 'WRONG',
        'observed_successor_hash': 'a' * 64,
        'continuity_state': 'healthy',
        'validation_reference': 'test-ref',
        'validation_statement': 'validated',
    })
    assert response.status_code == 403


def test_validation_required_before_recertification() -> None:
    response = client.post('/auron/demo1/v21.361/succession/recertify', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'recertification_phrase': 'RECERTIFY AURON TELEGRAM NEXT SUCCESSOR SUCCESSION',
        'recertification_reference': 'test-ref',
        'recertification_statement': 'recertified',
    })
    assert response.status_code == 409


def test_recertification_required_before_baseline_renewal() -> None:
    response = client.post('/auron/demo1/v21.361/baseline/renew', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'renewal_phrase': 'RENEW AURON TELEGRAM NEXT SUCCESSOR ASSURANCE BASELINE',
        'baseline_reference': 'test-ref',
        'audit_interval_days': 90,
    })
    assert response.status_code == 409
