from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.auron_demo1_telegram_successor_baseline_stabilization_v21_354 import (
    reset_telegram_successor_baseline_stabilization_store,
)

client = TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_baseline_stabilization_store()


def test_v21_354_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.354/status' in paths
    assert '/auron/demo1/v21.354/stabilization/start' in paths
    assert '/auron/demo1/v21.354/continuity/observe' in paths
    assert '/auron/demo1/v21.354/succession/certify' in paths


def test_status_is_safe_when_empty() -> None:
    response = client.get('/auron/demo1/v21.354/status')
    assert response.status_code == 200
    assert response.json() == {
        'stabilizations': 0,
        'continuity_observations': 0,
        'succession_certifications': 0,
        'failed_stabilizations': 0,
        'external_calls_made': 0,
        'mode': 'successor-baseline-stabilization-restored-continuity-observation-succession-certification',
    }


def test_start_requires_explicit_phrase() -> None:
    response = client.post(
        '/auron/demo1/v21.354/stabilization/start',
        json={
            'actor': 'operator',
            'continuity_id': 'continuity-1',
            'start_phrase': 'wrong',
            'stabilization_hours': 24,
            'minimum_observations': 2,
        },
    )
    assert response.status_code == 403


def test_certification_requires_existing_stabilization() -> None:
    response = client.post(
        '/auron/demo1/v21.354/succession/certify',
        json={
            'actor': 'auditor',
            'stabilization_id': 'missing',
            'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR BASELINE SUCCESSION',
            'certification_reference': 'cert-ref',
            'certification_statement': 'stable',
        },
    )
    assert response.status_code == 404
