from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_three_stabilization_v21_379 import (
    reset_telegram_successor_next_generation_three_stabilization_store,
    router,
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_three_stabilization_store()


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.379/stabilization/start' in paths
    assert '/auron/demo1/v21.379/continuity/observe' in paths
    assert '/auron/demo1/v21.379/succession/certify' in paths
    assert '/auron/demo1/v21.379/status' in paths
    assert '/auron/demo1/v21.379/command-center' in paths


def test_safe_empty_status() -> None:
    response = _client().get('/auron/demo1/v21.379/status')
    assert response.status_code == 200
    body = response.json()
    assert body['stabilizations'] == 0
    assert body['continuity_observations'] == 0
    assert body['succession_certifications'] == 0
    assert body['external_calls_made'] == 0


def test_explicit_stabilization_phrase_enforcement() -> None:
    response = _client().post(
        '/auron/demo1/v21.379/stabilization/start',
        json={
            'actor': 'tester',
            'continuity_monitor_id': 'continuity-1',
            'start_phrase': 'WRONG',
            'stabilization_hours': 168,
            'minimum_observations': 3,
        },
    )
    assert response.status_code == 403


def test_missing_stabilization_observation_blocking() -> None:
    response = _client().post(
        '/auron/demo1/v21.379/continuity/observe',
        json={
            'actor': 'tester',
            'stabilization_id': 'missing',
            'observation_phrase': 'OBSERVE AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE CONTINUITY',
            'observed_successor_next_generation_three_hash': 'a' * 64,
            'continuity_state': 'healthy',
            'statement': 'healthy observation',
        },
    )
    assert response.status_code == 404


def test_missing_stabilization_certification_blocking() -> None:
    response = _client().post(
        '/auron/demo1/v21.379/succession/certify',
        json={
            'actor': 'tester',
            'stabilization_id': 'missing',
            'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE SUCCESSION',
            'certification_reference': 'ref-1',
            'certification_statement': 'certification statement',
        },
    )
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = _client().get('/auron/demo1/v21.379/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION THREE STABILIZATION' in response.text
    assert 'no Telegram API call' in response.text
