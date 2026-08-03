from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_two_stabilization_v21_374 import (
    reset_telegram_successor_next_generation_two_stabilization_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_two_stabilization_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.374/stabilization/start' in paths
    assert '/auron/demo1/v21.374/continuity/observe' in paths
    assert '/auron/demo1/v21.374/succession/certify' in paths
    assert '/auron/demo1/v21.374/status' in paths
    assert '/auron/demo1/v21.374/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.374/status')
    assert response.status_code == 200
    assert response.json()['stabilizations'] == 0
    assert response.json()['external_calls_made'] == 0


def test_explicit_stabilization_phrase_enforced() -> None:
    response = client().post(
        '/auron/demo1/v21.374/stabilization/start',
        json={
            'actor': 'tester',
            'continuity_monitor_id': 'missing',
            'start_phrase': 'wrong',
        },
    )
    assert response.status_code == 403


def test_missing_stabilization_blocks_observation() -> None:
    response = client().post(
        '/auron/demo1/v21.374/continuity/observe',
        json={
            'actor': 'tester',
            'stabilization_id': 'missing',
            'observation_phrase': 'OBSERVE AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO CONTINUITY',
            'observed_successor_next_generation_two_hash': 'a' * 64,
            'continuity_state': 'healthy',
            'statement': 'healthy observation',
        },
    )
    assert response.status_code == 404


def test_missing_stabilization_blocks_certification() -> None:
    response = client().post(
        '/auron/demo1/v21.374/succession/certify',
        json={
            'actor': 'tester',
            'stabilization_id': 'missing',
            'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO SUCCESSION',
            'certification_reference': 'ref',
            'certification_statement': 'certify',
        },
    )
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.374/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION TWO STABILIZATION' in response.text
    assert 'no Telegram API call' in response.text
