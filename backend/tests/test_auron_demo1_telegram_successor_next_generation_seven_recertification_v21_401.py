from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_seven_recertification_v21_401 import (
    reset_telegram_successor_next_generation_seven_recertification_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_seven_recertification_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.401/remediation/validate' in paths
    assert '/auron/demo1/v21.401/succession/recertify' in paths
    assert '/auron/demo1/v21.401/baseline/renew' in paths
    assert '/auron/demo1/v21.401/status' in paths
    assert '/auron/demo1/v21.401/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.401/status')
    assert response.status_code == 200
    assert response.json() == {
        'validations': 0,
        'recertifications': 0,
        'renewed_baselines': 0,
        'external_calls_made': 0,
        'mode': 'successor-next-generation-seven-remediation-validation-recertification-renewed-baseline-governance',
    }


def test_explicit_validation_phrase_enforcement() -> None:
    response = client().post('/auron/demo1/v21.401/remediation/validate', json={
        'actor': 'tester',
        'monitoring_id': 'monitoring-missing',
        'drift_id': 'drift-missing',
        'validation_phrase': 'wrong',
        'observed_corrected_hash': 'a' * 64,
        'control_state': 'healthy',
        'validation_reference': 'VAL-1',
        'validation_statement': 'validation',
    })
    assert response.status_code == 403


def test_resolved_drift_required_for_validation() -> None:
    response = client().post('/auron/demo1/v21.401/remediation/validate', json={
        'actor': 'tester',
        'monitoring_id': 'monitoring-missing',
        'drift_id': 'drift-missing',
        'validation_phrase': 'VALIDATE AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN DRIFT REMEDIATION',
        'observed_corrected_hash': 'a' * 64,
        'control_state': 'healthy',
        'validation_reference': 'VAL-1',
        'validation_statement': 'validation',
    })
    assert response.status_code == 409


def test_validation_required_before_recertification() -> None:
    response = client().post('/auron/demo1/v21.401/succession/recertify', json={
        'actor': 'tester',
        'validation_id': 'validation-missing',
        'recertification_phrase': 'RECERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN SUCCESSION',
        'recertification_reference': 'RECERT-1',
        'recertification_statement': 'recertification',
    })
    assert response.status_code == 404


def test_recertification_required_before_baseline_renewal() -> None:
    response = client().post('/auron/demo1/v21.401/baseline/renew', json={
        'actor': 'tester',
        'recertification_id': 'recertification-missing',
        'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN ASSURANCE BASELINE',
        'renewed_successor_next_generation_seven_hash': 'b' * 64,
        'audit_interval_days': 30,
        'validity_days': 365,
        'renewal_reference': 'BASELINE-1',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.401/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION SEVEN RECERTIFICATION' in response.text
    assert 'no outbound message' in response.text
