from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_five_stabilization_v21_389 import (
    reset_telegram_successor_next_generation_five_stabilization_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_five_stabilization_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.389/stabilization/start' in paths
    assert '/auron/demo1/v21.389/continuity/observe' in paths
    assert '/auron/demo1/v21.389/succession/certify' in paths
    assert '/auron/demo1/v21.389/status' in paths
    assert '/auron/demo1/v21.389/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.389/status')
    assert response.status_code == 200
    assert response.json() == {
        'stabilizations': 0,
        'observations': 0,
        'certifications': 0,
        'external_calls_made': 0,
        'mode': 'successor-next-generation-five-stabilization-observation-certification-governance',
    }


def test_explicit_stabilization_phrase_enforced() -> None:
    response = client().post(
        '/auron/demo1/v21.389/stabilization/start',
        json={
            'actor': 'operator',
            'continuity_id': 'missing-continuity',
            'start_phrase': 'WRONG',
        },
    )
    assert response.status_code == 403


def test_missing_stabilization_blocks_observation() -> None:
    response = client().post(
        '/auron/demo1/v21.389/continuity/observe',
        json={
            'actor': 'operator',
            'stabilization_id': 'missing',
            'observation_phrase': 'OBSERVE AURON TELEGRAM SUCCESSOR NEXT GENERATION FIVE CONTINUITY',
            'observed_successor_next_generation_five_hash': 'a' * 64,
            'continuity_state': 'healthy',
            'statement': 'healthy observation',
        },
    )
    assert response.status_code == 404


def test_missing_stabilization_blocks_certification() -> None:
    response = client().post(
        '/auron/demo1/v21.389/succession/certify',
        json={
            'actor': 'operator',
            'stabilization_id': 'missing',
            'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION FIVE SUCCESSION',
            'certification_reference': 'ref-1',
            'certification_statement': 'certify only after healthy stabilization',
        },
    )
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.389/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION FIVE STABILIZATION' in response.text
    assert 'no Telegram API call' in response.text
