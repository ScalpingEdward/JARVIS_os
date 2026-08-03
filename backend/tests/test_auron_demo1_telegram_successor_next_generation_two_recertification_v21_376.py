from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_two_recertification_v21_376 import (
    reset_telegram_successor_next_generation_two_recertification_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_two_recertification_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.376/remediation/validate' in paths
    assert '/auron/demo1/v21.376/succession/recertify' in paths
    assert '/auron/demo1/v21.376/baseline/renew' in paths
    assert '/auron/demo1/v21.376/status' in paths
    assert '/auron/demo1/v21.376/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.376/status')
    assert response.status_code == 200
    assert response.json()['remediation_validations'] == 0
    assert response.json()['succession_recertifications'] == 0
    assert response.json()['renewed_baselines'] == 0
    assert response.json()['external_calls_made'] == 0


def test_explicit_validation_phrase_enforcement() -> None:
    response = client().post(
        '/auron/demo1/v21.376/remediation/validate',
        json={
            'actor': 'test',
            'monitoring_id': 'missing',
            'validation_phrase': 'WRONG',
            'observed_corrected_hash': 'a' * 64,
            'control_state': 'healthy',
            'validation_reference': 'ref',
            'validation_statement': 'statement',
        },
    )
    assert response.status_code == 403


def test_validation_required_before_recertification() -> None:
    response = client().post(
        '/auron/demo1/v21.376/succession/recertify',
        json={
            'actor': 'test',
            'monitoring_id': 'missing',
            'recertification_phrase': 'RECERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO SUCCESSION',
            'recertification_reference': 'ref',
            'recertification_statement': 'statement',
        },
    )
    assert response.status_code == 409


def test_recertification_required_before_baseline_renewal() -> None:
    response = client().post(
        '/auron/demo1/v21.376/baseline/renew',
        json={
            'actor': 'test',
            'monitoring_id': 'missing',
            'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO ASSURANCE BASELINE',
            'renewed_baseline_hash': 'b' * 64,
            'baseline_reference': 'ref',
            'audit_interval_days': 30,
        },
    )
    assert response.status_code == 409


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.376/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION TWO RECERTIFICATION' in response.text
    assert 'no outbound message' in response.text
