from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_expired_renewed_successor_next_generation_four_restoration_v21_388 import (
    reset_telegram_expired_renewed_successor_next_generation_four_restoration_store,
    router,
)


def client() -> TestClient:
    reset_telegram_expired_renewed_successor_next_generation_four_restoration_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.388/recertification/admit' in paths
    assert '/auron/demo1/v21.388/continuity/restore' in paths
    assert '/auron/demo1/v21.388/succession/establish' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.388/status')
    assert response.status_code == 200
    assert response.json()['external_calls_made'] == 0
    assert response.json()['admissions'] == 0


def test_explicit_admission_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.388/recertification/admit', json={
        'actor': 'operator',
        'continuity_id': 'continuity-1',
        'admission_phrase': 'wrong',
        'remediation_reference': 'REM-1',
        'remediation_statement': 'Remediation completed.',
    })
    assert response.status_code == 403


def test_expiry_evidence_required() -> None:
    response = client().post('/auron/demo1/v21.388/recertification/admit', json={
        'actor': 'operator',
        'continuity_id': 'continuity-1',
        'admission_phrase': 'ADMIT AURON TELEGRAM EXPIRED RENEWED SUCCESSOR NEXT GENERATION FOUR RECERTIFICATION',
        'remediation_reference': 'REM-1',
        'remediation_statement': 'Remediation completed.',
    })
    assert response.status_code == 409


def test_admission_required_before_restoration() -> None:
    response = client().post('/auron/demo1/v21.388/continuity/restore', json={
        'actor': 'operator',
        'continuity_id': 'continuity-1',
        'restoration_phrase': 'RESTORE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION FOUR CONTINUITY',
        'observed_expired_baseline_hash': 'a' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'RESTORE-1',
    })
    assert response.status_code == 409


def test_restoration_required_before_succession() -> None:
    response = client().post('/auron/demo1/v21.388/succession/establish', json={
        'actor': 'operator',
        'continuity_id': 'continuity-1',
        'establishment_phrase': 'ESTABLISH AURON TELEGRAM SUCCESSOR NEXT GENERATION FIVE BASELINE',
        'successor_next_generation_five_hash': 'b' * 64,
        'succession_reference': 'SUCCESSION-1',
    })
    assert response.status_code == 409


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.388/command-center')
    assert response.status_code == 200
    assert 'EXPIRED RENEWED SUCCESSOR NEXT GENERATION FOUR RESTORATION' in response.text
    assert 'no outbound message' in response.text
