from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_post_remediation_probation_certification_v21_349 import (
    router,
    reset_telegram_post_remediation_probation_certification_store,
)


def setup_function() -> None:
    reset_telegram_post_remediation_probation_certification_store()


def test_v21_349_routes_are_registered() -> None:
    app = FastAPI()
    app.include_router(router)
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.349/probation/start' in paths
    assert '/auron/demo1/v21.349/evidence/observe' in paths
    assert '/auron/demo1/v21.349/reclosure/certify' in paths
    assert '/auron/demo1/v21.349/status' in paths


def test_v21_349_status_is_safe_and_empty() -> None:
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get('/auron/demo1/v21.349/status')
    assert response.status_code == 200
    assert response.json()['probations'] == 0
    assert response.json()['observations'] == 0
    assert response.json()['certifications'] == 0
    assert response.json()['external_calls_made'] == 0


def test_probation_requires_explicit_phrase() -> None:
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post('/auron/demo1/v21.349/probation/start', json={
        'actor': 'tester',
        'record_id': 'record-1',
        'start_phrase': 'wrong',
        'probation_hours': 1,
        'minimum_observations': 1,
    })
    assert response.status_code == 403


def test_certification_requires_existing_probation() -> None:
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post('/auron/demo1/v21.349/reclosure/certify', json={
        'actor': 'tester',
        'probation_id': 'missing',
        'certification_phrase': 'CERTIFY AURON TELEGRAM GOVERNED RECLOSURE',
        'certification_reference': 'cert-1',
        'certification_statement': 'stable',
    })
    assert response.status_code == 404
