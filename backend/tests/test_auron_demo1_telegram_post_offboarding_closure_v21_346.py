from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.auron_demo1_telegram_post_offboarding_closure_v21_346 import (
    reset_telegram_post_offboarding_closure_store,
)

client = TestClient(app)


def setup_function() -> None:
    reset_telegram_post_offboarding_closure_store()


def test_v21_346_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.346/status' in paths
    assert '/auron/demo1/v21.346/archive' in paths
    assert '/auron/demo1/v21.346/risk-review' in paths
    assert '/auron/demo1/v21.346/close' in paths


def test_empty_status_is_safe() -> None:
    response = client.get('/auron/demo1/v21.346/status')
    assert response.status_code == 200
    assert response.json()['archives'] == 0
    assert response.json()['external_calls_made'] == 0


def test_archive_requires_explicit_phrase() -> None:
    response = client.post('/auron/demo1/v21.346/archive', json={
        'actor': 'tester',
        'retention_id': 'ret-1',
        'archive_phrase': 'wrong',
        'archive_reference': 'archive-1',
    })
    assert response.status_code == 403


def test_closure_requires_archive_and_review() -> None:
    response = client.post('/auron/demo1/v21.346/close', json={
        'actor': 'tester',
        'archive_id': 'archive-1',
        'closure_phrase': 'CLOSE AURON TELEGRAM DISCLOSURE LIFECYCLE',
        'closure_reference': 'closure-1',
    })
    assert response.status_code == 409
