from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_fourteen_restoration_v21_425 import (
    router,
    status,
)


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.425/restoration/prepare' in paths
    assert '/auron/demo1/v21.425/activation/execute' in paths
    assert '/auron/demo1/v21.425/succession/certify' in paths
    assert '/auron/demo1/v21.425/status' in paths
    assert '/auron/demo1/v21.425/command-center' in paths


def test_safe_empty_status() -> None:
    result = status()
    assert result['external_calls_made'] == 0
    assert result['restorations'] == 0
    assert result['activations'] == 0
    assert result['certifications'] == 0


def test_restoration_requires_explicit_phrase() -> None:
    response = client().post(
        '/auron/demo1/v21.425/restoration/prepare',
        json={
            'actor': 'tester',
            'renewal_request_id': 'renewal-1',
            'restoration_phrase': 'NO',
            'proposed_successor_next_generation_fourteen_hash': 'a' * 64,
            'control_state': 'healthy',
            'restoration_reference': 'test',
            'restoration_statement': 'test statement',
        },
    )
    assert response.status_code == 403


def test_activation_requires_explicit_phrase() -> None:
    response = client().post(
        '/auron/demo1/v21.425/activation/execute',
        json={
            'actor': 'tester',
            'restoration_id': 'restoration-1',
            'activation_phrase': 'NO',
            'observed_successor_next_generation_fourteen_hash': 'a' * 64,
            'control_state': 'healthy',
            'activation_reference': 'test',
            'activation_statement': 'test statement',
        },
    )
    assert response.status_code == 403


def test_certification_requires_explicit_phrase() -> None:
    response = client().post(
        '/auron/demo1/v21.425/succession/certify',
        json={
            'actor': 'tester',
            'activation_id': 'activation-1',
            'certification_phrase': 'NO',
            'certification_reference': 'test',
            'certification_statement': 'test statement',
        },
    )
    assert response.status_code == 403


def test_command_center_declares_safe_mode() -> None:
    response = client().get('/auron/demo1/v21.425/command-center')
    assert response.status_code == 200
    assert 'no Telegram API call' in response.text
    assert 'no provider execution' in response.text
    assert 'no outbound message' in response.text
