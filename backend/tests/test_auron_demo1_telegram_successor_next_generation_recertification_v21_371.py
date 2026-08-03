from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_recertification_v21_371 import (
    reset_telegram_successor_next_generation_recertification_store,
    router,
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_recertification_store()


def test_router_registration_and_empty_status() -> None:
    client = _client()
    paths = {route.path for route in client.app.routes}
    assert '/auron/demo1/v21.371/remediation/validate' in paths
    assert '/auron/demo1/v21.371/succession/recertify' in paths
    assert '/auron/demo1/v21.371/baseline/renew' in paths
    response = client.get('/auron/demo1/v21.371/status')
    assert response.status_code == 200
    assert response.json()['remediation_validations'] == 0
    assert response.json()['external_calls_made'] == 0


def test_validation_requires_explicit_phrase() -> None:
    client = _client()
    response = client.post(
        '/auron/demo1/v21.371/remediation/validate',
        json={
            'actor': 'test',
            'monitoring_id': 'missing',
            'validation_phrase': 'wrong',
            'observed_corrected_hash': 'a' * 64,
            'control_state': 'healthy',
            'validation_reference': 'ref',
            'validation_statement': 'statement',
        },
    )
    assert response.status_code == 403


def test_recertification_requires_validation() -> None:
    client = _client()
    response = client.post(
        '/auron/demo1/v21.371/succession/recertify',
        json={
            'actor': 'test',
            'monitoring_id': 'missing',
            'recertification_phrase': 'RECERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION SUCCESSION',
            'recertification_reference': 'ref',
            'recertification_statement': 'statement',
        },
    )
    assert response.status_code == 409


def test_baseline_renewal_requires_recertification() -> None:
    client = _client()
    response = client.post(
        '/auron/demo1/v21.371/baseline/renew',
        json={
            'actor': 'test',
            'monitoring_id': 'missing',
            'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION ASSURANCE BASELINE',
            'renewed_baseline_hash': 'b' * 64,
            'baseline_reference': 'ref',
            'audit_interval_days': 30,
        },
    )
    assert response.status_code == 409


def test_command_center_available() -> None:
    client = _client()
    response = client.get('/auron/demo1/v21.371/command-center')
    assert response.status_code == 200
    assert 'v21.371' in response.text
