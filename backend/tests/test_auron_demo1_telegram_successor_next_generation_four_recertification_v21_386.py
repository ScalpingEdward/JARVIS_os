from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_four_recertification_v21_386 import (
    reset_telegram_successor_next_generation_four_recertification_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_four_recertification_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.386/remediation/validate' in paths
    assert '/auron/demo1/v21.386/succession/recertify' in paths
    assert '/auron/demo1/v21.386/baseline/renew' in paths
    assert '/auron/demo1/v21.386/status' in paths
    assert '/auron/demo1/v21.386/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.386/status')
    assert response.status_code == 200
    assert response.json() == {
        'remediation_validations': 0,
        'succession_recertifications': 0,
        'renewed_baselines': 0,
        'external_calls_made': 0,
        'mode': 'successor-next-generation-four-recertification-renewed-baseline-governance',
    }


def test_explicit_validation_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.386/remediation/validate', json={
        'actor': 'operator',
        'monitoring_id': 'missing',
        'validation_phrase': 'WRONG',
        'observed_corrected_hash': 'a' * 64,
        'control_state': 'healthy',
        'validation_reference': 'ref',
        'validation_statement': 'statement',
    })
    assert response.status_code == 403


def test_validation_required_before_recertification() -> None:
    response = client().post('/auron/demo1/v21.386/succession/recertify', json={
        'actor': 'operator',
        'monitoring_id': 'missing',
        'recertification_phrase': 'RECERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION FOUR SUCCESSION',
        'recertification_reference': 'ref',
        'recertification_statement': 'statement',
    })
    assert response.status_code == 409


def test_recertification_required_before_baseline_renewal() -> None:
    response = client().post('/auron/demo1/v21.386/baseline/renew', json={
        'actor': 'operator',
        'monitoring_id': 'missing',
        'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION FOUR ASSURANCE BASELINE',
        'renewed_successor_next_generation_four_hash': 'b' * 64,
        'baseline_reference': 'ref',
    })
    assert response.status_code == 409


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.386/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION FOUR RECERTIFICATION' in response.text
    assert 'no outbound message' in response.text
