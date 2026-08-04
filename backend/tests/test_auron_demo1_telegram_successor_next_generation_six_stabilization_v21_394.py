from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_six_stabilization_v21_394 import (
    reset_telegram_successor_next_generation_six_stabilization_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_six_stabilization_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.394/stabilization/start' in paths
    assert '/auron/demo1/v21.394/continuity/observe' in paths
    assert '/auron/demo1/v21.394/succession/certify' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.394/status')
    assert response.status_code == 200
    assert response.json()['external_calls_made'] == 0
    assert response.json()['stabilizations'] == 0


def test_explicit_stabilization_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.394/stabilization/start', json={
        'actor': 'operator',
        'continuity_id': 'continuity-1',
        'start_phrase': 'wrong',
        'stabilization_window_days': 30,
        'minimum_healthy_observations': 3,
    })
    assert response.status_code == 403


def test_v21393_succession_required() -> None:
    response = client().post('/auron/demo1/v21.394/stabilization/start', json={
        'actor': 'operator',
        'continuity_id': 'continuity-1',
        'start_phrase': 'START AURON TELEGRAM SUCCESSOR NEXT GENERATION SIX STABILIZATION',
        'stabilization_window_days': 30,
        'minimum_healthy_observations': 3,
    })
    assert response.status_code == 409


def test_stabilization_required_before_observation() -> None:
    response = client().post('/auron/demo1/v21.394/continuity/observe', json={
        'actor': 'operator',
        'stabilization_id': 'stabilization-1',
        'observation_phrase': 'OBSERVE AURON TELEGRAM SUCCESSOR NEXT GENERATION SIX CONTINUITY',
        'observed_successor_next_generation_six_hash': 'a' * 64,
        'continuity_state': 'healthy',
        'statement': 'Continuity healthy.',
    })
    assert response.status_code == 404


def test_stabilization_required_before_certification() -> None:
    response = client().post('/auron/demo1/v21.394/succession/certify', json={
        'actor': 'operator',
        'stabilization_id': 'stabilization-1',
        'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION SIX SUCCESSION',
        'certification_reference': 'CERT-1',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.394/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION SIX STABILIZATION' in response.text
    assert 'no outbound message' in response.text
