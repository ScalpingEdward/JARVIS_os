from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_expired_renewed_successor_next_generation_eight_restoration_v21_408 import (
    reset_telegram_expired_renewed_successor_next_generation_eight_restoration_store,
    router,
)
from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_eight_continuity_v21_407 import (
    _continuity_store,
    _expiry_store,
)


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_expired_renewed_successor_next_generation_eight_restoration_store()
    _continuity_store.clear()
    _expiry_store.clear()


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.408/recertification/admit' in paths
    assert '/auron/demo1/v21.408/continuity/restore' in paths
    assert '/auron/demo1/v21.408/successor/baseline/establish' in paths
    assert '/auron/demo1/v21.408/status' in paths
    assert '/auron/demo1/v21.408/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.408/status')
    assert response.status_code == 200
    assert response.json() == {
        'admissions': 0,
        'restorations': 0,
        'successions': 0,
        'external_calls_made': 0,
        'mode': 'expired-renewed-successor-next-generation-eight-restoration-succession-governance',
    }


def test_explicit_admission_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.408/recertification/admit', json={
        'actor': 'tester',
        'continuity_id': 'continuity-1',
        'admission_phrase': 'NO',
        'remediation_reference': 'ticket-1',
        'remediation_statement': 'remediated',
    })
    assert response.status_code == 403


def test_expiry_evidence_required() -> None:
    response = client().post('/auron/demo1/v21.408/recertification/admit', json={
        'actor': 'tester',
        'continuity_id': 'continuity-1',
        'admission_phrase': 'ADMIT AURON TELEGRAM EXPIRED RENEWED SUCCESSOR NEXT GENERATION EIGHT RECERTIFICATION',
        'remediation_reference': 'ticket-1',
        'remediation_statement': 'remediated',
    })
    assert response.status_code == 409


def test_admission_required_before_restoration() -> None:
    response = client().post('/auron/demo1/v21.408/continuity/restore', json={
        'actor': 'tester',
        'admission_id': 'missing',
        'restoration_phrase': 'RESTORE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION EIGHT CONTINUITY',
        'observed_expired_hash': 'a' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'restore-1',
    })
    assert response.status_code == 404


def test_restoration_required_before_succession() -> None:
    response = client().post('/auron/demo1/v21.408/successor/baseline/establish', json={
        'actor': 'tester',
        'restoration_id': 'missing',
        'succession_phrase': 'ESTABLISH AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE BASELINE',
        'successor_next_generation_nine_hash': 'b' * 64,
        'health_check_interval_days': 30,
        'validity_days': 365,
        'succession_reference': 'succession-1',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.408/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION EIGHT RESTORATION COMMAND CENTER' in response.text
