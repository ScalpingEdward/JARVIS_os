from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_expired_renewed_successor_next_generation_seven_restoration_v21_403 import (
    reset_telegram_expired_renewed_successor_next_generation_seven_restoration_store,
    router,
)


def client() -> TestClient:
    reset_telegram_expired_renewed_successor_next_generation_seven_restoration_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.403/recertification/admit' in paths
    assert '/auron/demo1/v21.403/continuity/restore' in paths
    assert '/auron/demo1/v21.403/successor/baseline/establish' in paths
    assert '/auron/demo1/v21.403/status' in paths
    assert '/auron/demo1/v21.403/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.403/status')
    assert response.status_code == 200
    assert response.json() == {
        'admissions': 0,
        'restorations': 0,
        'successions': 0,
        'external_calls_made': 0,
        'mode': 'expired-renewed-successor-next-generation-seven-restoration-succession-governance',
    }


def test_explicit_admission_phrase_enforcement() -> None:
    response = client().post('/auron/demo1/v21.403/recertification/admit', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'admission_phrase': 'wrong',
        'remediation_reference': 'REM-1',
        'remediation_statement': 'remediation',
    })
    assert response.status_code == 403


def test_expiry_evidence_required_for_admission() -> None:
    response = client().post('/auron/demo1/v21.403/recertification/admit', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'admission_phrase': 'ADMIT AURON TELEGRAM EXPIRED RENEWED SUCCESSOR NEXT GENERATION SEVEN RECERTIFICATION',
        'remediation_reference': 'REM-1',
        'remediation_statement': 'remediation',
    })
    assert response.status_code == 409


def test_admission_required_before_restoration() -> None:
    response = client().post('/auron/demo1/v21.403/continuity/restore', json={
        'actor': 'tester',
        'admission_id': 'missing',
        'restoration_phrase': 'RESTORE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION SEVEN CONTINUITY',
        'observed_expired_hash': 'a' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'REST-1',
    })
    assert response.status_code == 404


def test_restoration_required_before_succession() -> None:
    response = client().post('/auron/demo1/v21.403/successor/baseline/establish', json={
        'actor': 'tester',
        'restoration_id': 'missing',
        'succession_phrase': 'ESTABLISH AURON TELEGRAM SUCCESSOR NEXT GENERATION EIGHT BASELINE',
        'successor_next_generation_eight_hash': 'b' * 64,
        'health_check_interval_days': 30,
        'validity_days': 365,
        'succession_reference': 'SUC-1',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.403/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION SEVEN RESTORATION' in response.text
    assert 'no outbound message' in response.text
