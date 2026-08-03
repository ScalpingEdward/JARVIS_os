from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_expired_renewed_successor_next_generation_two_restoration_v21_378 import (
    reset_telegram_expired_renewed_successor_next_generation_two_restoration_store,
    router,
)


def client() -> TestClient:
    reset_telegram_expired_renewed_successor_next_generation_two_restoration_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.378/recertification/admit' in paths
    assert '/auron/demo1/v21.378/continuity/restore' in paths
    assert '/auron/demo1/v21.378/baseline/establish' in paths
    assert '/auron/demo1/v21.378/status' in paths
    assert '/auron/demo1/v21.378/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.378/status')
    assert response.status_code == 200
    assert response.json()['recertification_admissions'] == 0
    assert response.json()['continuity_restorations'] == 0
    assert response.json()['successor_baselines'] == 0
    assert response.json()['external_calls_made'] == 0


def test_explicit_admission_phrase_required() -> None:
    response = client().post('/auron/demo1/v21.378/recertification/admit', json={
        'actor': 'tester',
        'continuity_monitor_id': 'missing',
        'admission_phrase': 'wrong',
        'remediation_reference': 'ref',
        'remediation_statement': 'statement',
    })
    assert response.status_code == 403


def test_expiry_evidence_required() -> None:
    response = client().post('/auron/demo1/v21.378/recertification/admit', json={
        'actor': 'tester',
        'continuity_monitor_id': 'missing',
        'admission_phrase': 'ADMIT AURON TELEGRAM EXPIRED RENEWED SUCCESSOR NEXT GENERATION TWO RECERTIFICATION',
        'remediation_reference': 'ref',
        'remediation_statement': 'statement',
    })
    assert response.status_code == 409


def test_admission_required_before_restoration() -> None:
    response = client().post('/auron/demo1/v21.378/continuity/restore', json={
        'actor': 'tester',
        'continuity_monitor_id': 'missing',
        'restoration_phrase': 'RESTORE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION TWO CONTINUITY',
        'observed_expired_hash': 'a' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'ref',
        'restoration_statement': 'statement',
    })
    assert response.status_code == 409


def test_restoration_required_before_succession() -> None:
    response = client().post('/auron/demo1/v21.378/baseline/establish', json={
        'actor': 'tester',
        'continuity_monitor_id': 'missing',
        'establishment_phrase': 'ESTABLISH AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE BASELINE',
        'successor_next_generation_three_hash': 'b' * 64,
        'baseline_reference': 'ref',
    })
    assert response.status_code == 409


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.378/command-center')
    assert response.status_code == 200
    assert 'EXPIRED RENEWED SUCCESSOR NEXT GENERATION TWO RESTORATION' in response.text
