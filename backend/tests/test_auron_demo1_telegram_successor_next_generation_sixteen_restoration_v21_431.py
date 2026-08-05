from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_sixteen_restoration_v21_431 import (
    router,
    status,
)


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.431/restoration/prepare' in paths
    assert '/auron/demo1/v21.431/activation/execute' in paths
    assert '/auron/demo1/v21.431/succession/certify' in paths
    assert '/auron/demo1/v21.431/status' in paths
    assert '/auron/demo1/v21.431/command-center' in paths


def test_safe_empty_status() -> None:
    result = status()
    assert result['external_calls_made'] == 0
    assert result['mode'] == 'successor-next-generation-sixteen-restoration-activation-succession'


def test_explicit_restoration_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.431/restoration/prepare', json={
        'actor': 'tester',
        'renewal_request_id': 'missing',
        'restoration_phrase': 'WRONG',
        'proposed_successor_next_generation_sixteen_hash': 'a' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'test',
        'restoration_statement': 'test',
    })
    assert response.status_code == 403


def test_explicit_activation_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.431/activation/execute', json={
        'actor': 'tester',
        'restoration_id': 'missing',
        'activation_phrase': 'WRONG',
        'observed_successor_next_generation_sixteen_hash': 'a' * 64,
        'control_state': 'healthy',
        'activation_reference': 'test',
        'activation_statement': 'test',
    })
    assert response.status_code == 403


def test_explicit_certification_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.431/succession/certify', json={
        'actor': 'tester',
        'activation_id': 'missing',
        'certification_phrase': 'WRONG',
        'certification_reference': 'test',
        'certification_statement': 'test',
    })
    assert response.status_code == 403


def test_command_center_safe_mode() -> None:
    response = client().get('/auron/demo1/v21.431/command-center')
    assert response.status_code == 200
    assert 'no Telegram API call' in response.text
    assert 'no provider execution' in response.text
    assert 'no outbound message' in response.text
