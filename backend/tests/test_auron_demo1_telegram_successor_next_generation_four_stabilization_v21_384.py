from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_four_stabilization_v21_384 import (
    reset_telegram_successor_next_generation_four_stabilization_store,
    router,
)


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_four_stabilization_store()


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.384/stabilization/start' in paths
    assert '/auron/demo1/v21.384/continuity/observe' in paths
    assert '/auron/demo1/v21.384/succession/certify' in paths
    assert '/auron/demo1/v21.384/status' in paths
    assert '/auron/demo1/v21.384/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.384/status')
    assert response.status_code == 200
    body = response.json()
    assert body['stabilizations'] == 0
    assert body['observations'] == 0
    assert body['certifications'] == 0
    assert body['external_calls_made'] == 0


def test_explicit_stabilization_phrase_enforced() -> None:
    response = client().post(
        '/auron/demo1/v21.384/stabilization/start',
        json={
            'actor': 'tester',
            'continuity_id': 'missing-continuity',
            'start_phrase': 'WRONG',
            'stabilization_window_hours': 24,
            'minimum_healthy_observations': 3,
        },
    )
    assert response.status_code == 403


def test_missing_stabilization_blocks_observation() -> None:
    response = client().post(
        '/auron/demo1/v21.384/continuity/observe',
        json={
            'actor': 'tester',
            'stabilization_id': 'missing',
            'observation_phrase': 'OBSERVE AURON TELEGRAM SUCCESSOR NEXT GENERATION FOUR CONTINUITY',
            'observed_successor_next_generation_four_hash': 'a' * 64,
            'continuity_state': 'healthy',
            'statement': 'healthy',
        },
    )
    assert response.status_code == 404


def test_missing_stabilization_blocks_certification() -> None:
    response = client().post(
        '/auron/demo1/v21.384/succession/certify',
        json={
            'actor': 'tester',
            'stabilization_id': 'missing',
            'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION FOUR SUCCESSION',
            'certification_reference': 'ref-1',
            'certification_statement': 'certify',
        },
    )
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.384/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION FOUR STABILIZATION' in response.text
    assert 'no outbound message' in response.text
