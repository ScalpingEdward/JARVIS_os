from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_assurance_recertification_v21_351 import (
    reset_telegram_assurance_recertification_store,
    router,
)


def setup_function() -> None:
    reset_telegram_assurance_recertification_store()


def test_v21_351_routes_are_registered() -> None:
    app = FastAPI()
    app.include_router(router)
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.351/drift-remediation/validate' in paths
    assert '/auron/demo1/v21.351/recertify' in paths
    assert '/auron/demo1/v21.351/baseline/renew' in paths
    assert '/auron/demo1/v21.351/status' in paths


def test_status_is_safe_and_empty() -> None:
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get('/auron/demo1/v21.351/status')
    assert response.status_code == 200
    assert response.json() == {
        'drift_remediation_validations': 0,
        'assurance_recertifications': 0,
        'renewed_assurance_baselines': 0,
        'external_calls_made': 0,
        'mode': 'assurance-recertification-drift-remediation-validation-renewed-baseline-governance',
    }


def test_validation_requires_explicit_phrase() -> None:
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post('/auron/demo1/v21.351/drift-remediation/validate', json={
        'actor': 'tester',
        'assurance_id': 'missing',
        'validation_phrase': 'wrong',
        'validation_reference': 'VAL-1',
        'validation_statement': 'Controls are healthy.',
        'observed_evidence_hash': 'a' * 64,
        'control_state': 'healthy',
    })
    assert response.status_code == 403


def test_recertification_requires_completed_validation() -> None:
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post('/auron/demo1/v21.351/recertify', json={
        'actor': 'tester',
        'assurance_id': 'missing',
        'recertification_phrase': 'RECERTIFY AURON TELEGRAM CERTIFIED RECLOSURE ASSURANCE',
        'recertification_reference': 'RECERT-1',
        'recertification_statement': 'Recertification decision.',
    })
    assert response.status_code == 409
