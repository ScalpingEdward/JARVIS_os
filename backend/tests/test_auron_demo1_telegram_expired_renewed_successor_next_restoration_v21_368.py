from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_expired_renewed_successor_next_restoration_v21_368 import (
    reset_telegram_expired_renewed_successor_next_restoration_store,
    router,
)


def client() -> TestClient:
    reset_telegram_expired_renewed_successor_next_restoration_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.368/recertification/admit' in paths
    assert '/auron/demo1/v21.368/continuity/restore' in paths
    assert '/auron/demo1/v21.368/baseline/succeed' in paths
    assert '/auron/demo1/v21.368/status' in paths
    assert '/auron/demo1/v21.368/command-center' in paths


def test_status_is_safe_and_empty() -> None:
    response = client().get('/auron/demo1/v21.368/status')
    assert response.status_code == 200
    assert response.json() == {
        'recertification_admissions': 0,
        'continuity_restorations': 0,
        'successor_next_generation_baselines': 0,
        'external_calls_made': 0,
        'mode': 'expired-renewed-successor-next-recertification-admission-continuity-restoration-succession-governance',
    }


def test_admission_requires_explicit_phrase() -> None:
    response = client().post(
        '/auron/demo1/v21.368/recertification/admit',
        json={
            'actor': 'operator',
            'continuity_id': 'continuity-1',
            'admission_phrase': 'wrong',
            'admission_reference': 'REF-1',
            'remediation_statement': 'Controls remediated.',
        },
    )
    assert response.status_code == 403
    assert response.json()['detail'] == 'Explicit expired renewed successor-next recertification admission required'


def test_restoration_requires_admission() -> None:
    response = client().post(
        '/auron/demo1/v21.368/continuity/restore',
        json={
            'actor': 'operator',
            'continuity_id': 'continuity-1',
            'restoration_phrase': 'RESTORE AURON TELEGRAM RENEWED SUCCESSOR NEXT CONTINUITY',
            'observed_expired_baseline_hash': 'a' * 64,
            'control_state': 'healthy',
            'restoration_reference': 'REF-2',
            'restoration_statement': 'Continuity restored.',
        },
    )
    assert response.status_code == 409
    assert response.json()['detail'] == 'Recertification admission required before continuity restoration'


def test_succession_requires_completed_restoration() -> None:
    response = client().post(
        '/auron/demo1/v21.368/baseline/succeed',
        json={
            'actor': 'operator',
            'continuity_id': 'continuity-1',
            'succession_phrase': 'ESTABLISH AURON TELEGRAM SUCCESSOR NEXT GENERATION BASELINE',
            'successor_reference': 'REF-3',
            'successor_next_generation_hash': 'b' * 64,
            'validity_days': 365,
            'health_interval_days': 30,
        },
    )
    assert response.status_code == 409
    assert response.json()['detail'] == 'Completed continuity restoration required before successor baseline succession'
