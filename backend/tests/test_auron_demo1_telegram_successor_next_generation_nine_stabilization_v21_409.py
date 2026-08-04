from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_expired_renewed_successor_next_generation_eight_restoration_v21_408 import (
    _succession_store,
    reset_telegram_expired_renewed_successor_next_generation_eight_restoration_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_nine_stabilization_v21_409 import (
    reset_telegram_successor_next_generation_nine_stabilization_store,
    router,
)


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_expired_renewed_successor_next_generation_eight_restoration_store()
    reset_telegram_successor_next_generation_nine_stabilization_store()


def test_route_registration_and_safe_status() -> None:
    response = client().get('/auron/demo1/v21.409/status')
    assert response.status_code == 200
    assert response.json()['external_calls_made'] == 0


def test_start_requires_explicit_phrase() -> None:
    response = client().post('/auron/demo1/v21.409/stabilization/start', json={
        'actor': 'tester', 'succession_id': 'missing', 'start_phrase': 'wrong'
    })
    assert response.status_code == 403


def test_start_requires_v21408_succession() -> None:
    response = client().post('/auron/demo1/v21.409/stabilization/start', json={
        'actor': 'tester',
        'succession_id': 'missing',
        'start_phrase': 'START AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE STABILIZATION'
    })
    assert response.status_code == 409


def test_observation_requires_stabilization() -> None:
    response = client().post('/auron/demo1/v21.409/continuity/observe', json={
        'actor': 'tester',
        'stabilization_id': 'missing',
        'observation_phrase': 'OBSERVE AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE CONTINUITY',
        'observed_successor_next_generation_nine_hash': 'a' * 64,
        'control_state': 'healthy',
        'observation_statement': 'healthy'
    })
    assert response.status_code == 404


def test_certification_requires_stabilization() -> None:
    response = client().post('/auron/demo1/v21.409/succession/certify', json={
        'actor': 'tester',
        'stabilization_id': 'missing',
        'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE SUCCESSION',
        'certification_reference': 'ref',
        'certification_statement': 'statement'
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.409/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION NINE STABILIZATION' in response.text
