from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_stabilization_v21_369 import (
    reset_telegram_successor_next_generation_stabilization_store,
    router,
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_stabilization_store()


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.369/stabilization/start' in paths
    assert '/auron/demo1/v21.369/continuity/observe' in paths
    assert '/auron/demo1/v21.369/succession/certify' in paths
    assert '/auron/demo1/v21.369/status' in paths
    assert '/auron/demo1/v21.369/command-center' in paths


def test_safe_empty_status() -> None:
    response = _client().get('/auron/demo1/v21.369/status')
    assert response.status_code == 200
    assert response.json() == {
        'stabilizations': 0,
        'continuity_observations': 0,
        'succession_certifications': 0,
        'failed_stabilizations': 0,
        'external_calls_made': 0,
        'mode': 'successor-next-generation-baseline-stabilization-continuity-observation-succession-certification',
    }


def test_explicit_stabilization_phrase_enforced() -> None:
    response = _client().post(
        '/auron/demo1/v21.369/stabilization/start',
        json={
            'actor': 'operator',
            'continuity_id': 'continuity-1',
            'start_phrase': 'wrong phrase',
            'stabilization_hours': 168,
            'minimum_observations': 3,
        },
    )
    assert response.status_code == 403
    assert response.json()['detail'] == (
        'Explicit successor-next-generation stabilization approval required'
    )


def test_observation_requires_existing_stabilization() -> None:
    response = _client().post(
        '/auron/demo1/v21.369/continuity/observe',
        json={
            'actor': 'operator',
            'stabilization_id': 'missing',
            'observation_phrase': 'OBSERVE AURON TELEGRAM SUCCESSOR NEXT GENERATION CONTINUITY',
            'observed_successor_next_generation_hash': 'a' * 64,
            'continuity_state': 'healthy',
            'statement': 'healthy observation',
        },
    )
    assert response.status_code == 404
    assert response.json()['detail'] == 'Successor-next-generation stabilization not found'


def test_certification_requires_existing_stabilization() -> None:
    response = _client().post(
        '/auron/demo1/v21.369/succession/certify',
        json={
            'actor': 'operator',
            'stabilization_id': 'missing',
            'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION SUCCESSION',
            'certification_reference': 'CERT-369',
            'certification_statement': 'certify stable succession',
        },
    )
    assert response.status_code == 404
    assert response.json()['detail'] == 'Successor-next-generation stabilization not found'


def test_command_center_available_without_external_calls() -> None:
    response = _client().get('/auron/demo1/v21.369/command-center')
    assert response.status_code == 200
    assert 'v21.369' in response.text
