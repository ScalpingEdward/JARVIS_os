from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_nine_monitoring_v21_410 import (
    reset_telegram_successor_next_generation_nine_monitoring_store,
    router,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_nine_stabilization_v21_409 import (
    _certification_store,
    reset_telegram_successor_next_generation_nine_stabilization_store,
)


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_nine_monitoring_store()
    reset_telegram_successor_next_generation_nine_stabilization_store()


def seed_certification() -> str:
    certification_id = 'cert-v21-409'
    _certification_store['stabilization-v21-409'] = {
        'certification_id': certification_id,
        'certification_state': 'successor-next-generation-nine-succession-certified-stable',
        'active_successor_next_generation_nine_hash': 'a' * 64,
        'integrity_hash': 'b' * 64,
        'immutable': True,
    }
    return certification_id


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.410/monitoring/start' in paths
    assert '/auron/demo1/v21.410/health/audit' in paths
    assert '/auron/demo1/v21.410/drift/open' in paths
    assert '/auron/demo1/v21.410/drift/resolve' in paths
    assert '/auron/demo1/v21.410/status' in paths
    assert '/auron/demo1/v21.410/command-center' in paths


def test_safe_empty_status() -> None:
    response = build_client().get('/auron/demo1/v21.410/status')
    assert response.status_code == 200
    assert response.json() == {
        'monitorings': 0,
        'audits': 0,
        'drifts': 0,
        'resolutions': 0,
        'external_calls_made': 0,
        'mode': 'certified-successor-next-generation-nine-monitoring-audit-drift-governance',
    }


def test_monitoring_requires_explicit_phrase() -> None:
    certification_id = seed_certification()
    response = build_client().post('/auron/demo1/v21.410/monitoring/start', json={
        'actor': 'master-brano',
        'certification_id': certification_id,
        'start_phrase': 'wrong phrase',
    })
    assert response.status_code == 403


def test_monitoring_requires_v21_409_certification() -> None:
    response = build_client().post('/auron/demo1/v21.410/monitoring/start', json={
        'actor': 'master-brano',
        'certification_id': 'missing',
        'start_phrase': 'START AURON TELEGRAM CERTIFIED SUCCESSOR NEXT GENERATION NINE MONITORING',
    })
    assert response.status_code == 409


def test_audit_requires_monitoring() -> None:
    response = build_client().post('/auron/demo1/v21.410/health/audit', json={
        'actor': 'master-brano',
        'monitoring_id': 'missing',
        'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE HEALTH',
        'observed_successor_next_generation_nine_hash': 'a' * 64,
        'control_state': 'healthy',
        'audit_statement': 'Healthy audit.',
    })
    assert response.status_code == 404


def test_drift_open_requires_monitoring() -> None:
    response = build_client().post('/auron/demo1/v21.410/drift/open', json={
        'actor': 'master-brano',
        'monitoring_id': 'missing',
        'trigger_audit_id': 'missing',
        'open_phrase': 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE DRIFT',
        'drift_reference': 'DRIFT-410',
        'drift_statement': 'Detected drift.',
    })
    assert response.status_code == 404


def test_resolution_requires_open_drift() -> None:
    response = build_client().post('/auron/demo1/v21.410/drift/resolve', json={
        'actor': 'master-brano',
        'drift_id': 'missing',
        'resolution_phrase': 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE DRIFT',
        'corrected_successor_next_generation_nine_hash': 'a' * 64,
        'control_state': 'healthy',
        'resolution_reference': 'RES-410',
        'resolution_statement': 'Resolved drift.',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = build_client().get('/auron/demo1/v21.410/command-center')
    assert response.status_code == 200
    assert 'AURON TELEGRAM CERTIFIED SUCCESSOR NEXT GENERATION NINE MONITORING COMMAND CENTER' in response.text
    assert 'no outbound message' in response.text
