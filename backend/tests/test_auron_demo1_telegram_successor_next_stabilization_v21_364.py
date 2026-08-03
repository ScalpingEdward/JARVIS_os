from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_stabilization_v21_364 import (
    reset_telegram_successor_next_stabilization_store,
    router,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_stabilization_store()


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.364/status' in paths
    assert '/auron/demo1/v21.364/stabilization/start' in paths
    assert '/auron/demo1/v21.364/continuity/observe' in paths
    assert '/auron/demo1/v21.364/succession/certify' in paths


def test_safe_empty_status() -> None:
    response = client.get('/auron/demo1/v21.364/status')
    assert response.status_code == 200
    body = response.json()
    assert body['stabilizations'] == 0
    assert body['continuity_observations'] == 0
    assert body['succession_certifications'] == 0
    assert body['external_calls_made'] == 0


def test_explicit_start_phrase_enforced() -> None:
    response = client.post('/auron/demo1/v21.364/stabilization/start', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'start_phrase': 'WRONG',
        'stabilization_hours': 168,
        'minimum_observations': 3,
    })
    assert response.status_code == 403


def test_missing_stabilization_blocks_observation() -> None:
    response = client.post('/auron/demo1/v21.364/continuity/observe', json={
        'actor': 'tester',
        'stabilization_id': 'missing',
        'observation_phrase': 'OBSERVE AURON TELEGRAM SUCCESSOR NEXT CONTINUITY',
        'observed_successor_next_hash': 'a' * 64,
        'continuity_state': 'healthy',
        'statement': 'healthy',
    })
    assert response.status_code == 404


def test_missing_stabilization_blocks_certification() -> None:
    response = client.post('/auron/demo1/v21.364/succession/certify', json={
        'actor': 'tester',
        'stabilization_id': 'missing',
        'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT SUCCESSION',
        'certification_reference': 'test-ref',
        'certification_statement': 'stable',
    })
    assert response.status_code == 404
