from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_seven_stabilization_v21_399 import (
    reset_telegram_successor_next_generation_seven_stabilization_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_seven_stabilization_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.399/stabilization/start' in paths
    assert '/auron/demo1/v21.399/continuity/observe' in paths
    assert '/auron/demo1/v21.399/succession/certify' in paths
    assert '/auron/demo1/v21.399/status' in paths
    assert '/auron/demo1/v21.399/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.399/status')
    assert response.status_code == 200
    assert response.json()['stabilizations'] == 0
    assert response.json()['observations'] == 0
    assert response.json()['certifications'] == 0
    assert response.json()['external_calls_made'] == 0


def test_explicit_stabilization_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.399/stabilization/start', json={
        'actor': 'tester',
        'succession_id': 'succession-missing',
        'start_phrase': 'wrong',
        'stabilization_window_days': 30,
        'minimum_healthy_observations': 3,
    })
    assert response.status_code == 403


def test_v21398_succession_required() -> None:
    response = client().post('/auron/demo1/v21.399/stabilization/start', json={
        'actor': 'tester',
        'succession_id': 'succession-missing',
        'start_phrase': 'START AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN STABILIZATION',
        'stabilization_window_days': 30,
        'minimum_healthy_observations': 3,
    })
    assert response.status_code == 409


def test_stabilization_required_before_observation() -> None:
    response = client().post('/auron/demo1/v21.399/continuity/observe', json={
        'actor': 'tester',
        'stabilization_id': 'stabilization-missing',
        'observation_phrase': 'OBSERVE AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN CONTINUITY',
        'observed_successor_next_generation_seven_hash': 'a' * 64,
        'continuity_state': 'healthy',
        'observation_statement': 'healthy observation',
    })
    assert response.status_code == 404


def test_stabilization_required_before_certification() -> None:
    response = client().post('/auron/demo1/v21.399/succession/certify', json={
        'actor': 'tester',
        'stabilization_id': 'stabilization-missing',
        'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN SUCCESSION',
        'certification_reference': 'CERT-1',
        'certification_statement': 'certify stable succession',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.399/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION SEVEN STABILIZATION' in response.text
    assert 'no outbound message' in response.text
