from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_eight_recertification_v21_406 import (
    reset_telegram_successor_next_generation_eight_recertification_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_eight_recertification_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_routes_and_empty_status_are_safe() -> None:
    api = client()
    response = api.get('/auron/demo1/v21.406/status')
    assert response.status_code == 200
    assert response.json() == {
        'validations': 0,
        'recertifications': 0,
        'renewed_baselines': 0,
        'external_calls_made': 0,
        'mode': 'successor-next-generation-eight-remediation-validation-recertification-renewed-baseline-governance',
    }


def test_validation_requires_explicit_phrase() -> None:
    api = client()
    response = api.post('/auron/demo1/v21.406/drift/validate', json={
        'actor': 'operator',
        'resolution_id': 'resolution-1',
        'validation_phrase': 'NO',
        'observed_corrected_hash': 'a' * 64,
        'control_state': 'healthy',
        'validation_reference': 'VAL-1',
        'validation_statement': 'Validated.',
    })
    assert response.status_code == 403


def test_validation_requires_resolved_v21405_evidence() -> None:
    api = client()
    response = api.post('/auron/demo1/v21.406/drift/validate', json={
        'actor': 'operator',
        'resolution_id': 'missing',
        'validation_phrase': 'VALIDATE AURON TELEGRAM SUCCESSOR NEXT GENERATION EIGHT DRIFT REMEDIATION',
        'observed_corrected_hash': 'a' * 64,
        'control_state': 'healthy',
        'validation_reference': 'VAL-1',
        'validation_statement': 'Validated.',
    })
    assert response.status_code == 404


def test_recertification_requires_validation() -> None:
    api = client()
    response = api.post('/auron/demo1/v21.406/succession/recertify', json={
        'actor': 'operator',
        'validation_id': 'missing',
        'recertification_phrase': 'RECERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION EIGHT SUCCESSION',
        'recertification_reference': 'RECERT-1',
        'recertification_statement': 'Recertified.',
    })
    assert response.status_code == 404


def test_baseline_renewal_requires_recertification() -> None:
    api = client()
    response = api.post('/auron/demo1/v21.406/baseline/renew', json={
        'actor': 'operator',
        'recertification_id': 'missing',
        'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION EIGHT ASSURANCE BASELINE',
        'renewed_successor_next_generation_eight_hash': 'a' * 64,
        'audit_interval_days': 30,
        'validity_days': 365,
        'renewal_reference': 'BASE-1',
    })
    assert response.status_code == 404


def test_command_center_is_available() -> None:
    api = client()
    response = api.get('/auron/demo1/v21.406/command-center')
    assert response.status_code == 200
    assert 'AURON TELEGRAM SUCCESSOR NEXT GENERATION EIGHT RECERTIFICATION' in response.text
    assert 'no outbound message' in response.text
