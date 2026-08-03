from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_expired_renewed_successor_next_generation_restoration_v21_373 import (
    reset_telegram_expired_renewed_successor_next_generation_restoration_store,
    router,
)


def client() -> TestClient:
    reset_telegram_expired_renewed_successor_next_generation_restoration_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.373/recertification/admit' in paths
    assert '/auron/demo1/v21.373/continuity/restore' in paths
    assert '/auron/demo1/v21.373/baseline/establish' in paths
    assert '/auron/demo1/v21.373/status' in paths
    assert '/auron/demo1/v21.373/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.373/status')
    assert response.status_code == 200
    body = response.json()
    assert body['recertification_admissions'] == 0
    assert body['continuity_restorations'] == 0
    assert body['successor_baselines'] == 0
    assert body['external_calls_made'] == 0


def test_explicit_admission_phrase_enforced() -> None:
    response = client().post(
        '/auron/demo1/v21.373/recertification/admit',
        json={
            'actor': 'tester',
            'continuity_monitor_id': 'missing',
            'admission_phrase': 'WRONG',
            'remediation_reference': 'REF-1',
            'remediation_statement': 'Remediation completed.',
        },
    )
    assert response.status_code == 403


def test_admission_requires_expiry_evidence() -> None:
    response = client().post(
        '/auron/demo1/v21.373/recertification/admit',
        json={
            'actor': 'tester',
            'continuity_monitor_id': 'missing',
            'admission_phrase': 'ADMIT AURON TELEGRAM EXPIRED RENEWED SUCCESSOR NEXT GENERATION RECERTIFICATION',
            'remediation_reference': 'REF-1',
            'remediation_statement': 'Remediation completed.',
        },
    )
    assert response.status_code == 409


def test_restoration_requires_admission() -> None:
    response = client().post(
        '/auron/demo1/v21.373/continuity/restore',
        json={
            'actor': 'tester',
            'continuity_monitor_id': 'missing',
            'restoration_phrase': 'RESTORE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION CONTINUITY',
            'observed_expired_hash': 'a' * 64,
            'control_state': 'healthy',
            'restoration_reference': 'REST-1',
            'restoration_statement': 'Controls restored.',
        },
    )
    assert response.status_code == 409


def test_baseline_establishment_requires_restoration() -> None:
    response = client().post(
        '/auron/demo1/v21.373/baseline/establish',
        json={
            'actor': 'tester',
            'continuity_monitor_id': 'missing',
            'establishment_phrase': 'ESTABLISH AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO BASELINE',
            'successor_next_generation_two_hash': 'b' * 64,
            'baseline_reference': 'BASE-1',
            'health_check_interval_days': 30,
            'validity_days': 365,
        },
    )
    assert response.status_code == 409


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.373/command-center')
    assert response.status_code == 200
    assert 'EXPIRED RENEWED SUCCESSOR NEXT GENERATION RESTORATION' in response.text
    assert 'no outbound message' in response.text
