from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_ten_monitoring_v21_414 import (
    reset_telegram_successor_next_generation_ten_monitoring_store,
    router,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_ten_restoration_v21_413 import (
    _succession_store,
    reset_telegram_successor_next_generation_ten_restoration_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_nine_monitoring_v21_410 import (
    _monitoring_store,
    reset_telegram_successor_next_generation_nine_monitoring_store,
)


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_ten_monitoring_store()
    reset_telegram_successor_next_generation_ten_restoration_store()
    reset_telegram_successor_next_generation_nine_monitoring_store()


def seed_certification() -> str:
    certification_id = 'cert-v21-413'
    monitoring_id = 'legacy-monitor-v21-410'
    active_hash = 'a' * 64
    _monitoring_store['legacy-certification-key'] = {
        'monitoring_id': monitoring_id,
        'monitoring_state': 'certified-successor-next-generation-ten-monitoring-pending',
        'active_successor_next_generation_ten_hash': active_hash,
    }
    _succession_store['activation-v21-413'] = {
        'certification_id': certification_id,
        'monitoring_id': monitoring_id,
        'active_successor_next_generation_ten_hash': active_hash,
        'certification_state': 'successor-next-generation-ten-succession-certified-stable',
        'integrity_hash': 'b' * 64,
        'immutable': True,
    }
    return certification_id


def start_monitoring(client: TestClient) -> dict:
    response = client.post('/auron/demo1/v21.414/monitoring/start', json={
        'actor': 'master-brano',
        'certification_id': seed_certification(),
        'start_phrase': 'START AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN MONITORING',
        'audit_interval_days': 30,
    })
    assert response.status_code == 200
    return response.json()['monitoring']


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.414/monitoring/start' in paths
    assert '/auron/demo1/v21.414/health/audit' in paths
    assert '/auron/demo1/v21.414/drift/open' in paths
    assert '/auron/demo1/v21.414/baseline/certify' in paths
    assert '/auron/demo1/v21.414/status' in paths
    assert '/auron/demo1/v21.414/command-center' in paths


def test_safe_empty_status() -> None:
    response = build_client().get('/auron/demo1/v21.414/status')
    assert response.status_code == 200
    assert response.json() == {
        'monitorings': 0,
        'audits': 0,
        'drifts': 0,
        'renewed_baselines': 0,
        'external_calls_made': 0,
        'mode': 'successor-next-generation-ten-monitoring-drift-renewed-baseline-certification',
    }


def test_monitoring_requires_explicit_phrase() -> None:
    response = build_client().post('/auron/demo1/v21.414/monitoring/start', json={
        'actor': 'master-brano',
        'certification_id': seed_certification(),
        'start_phrase': 'wrong phrase',
    })
    assert response.status_code == 403


def test_healthy_audit_and_baseline_certification_flow() -> None:
    client = build_client()
    monitoring = start_monitoring(client)
    audit = client.post('/auron/demo1/v21.414/health/audit', json={
        'actor': 'master-brano',
        'monitoring_id': monitoring['monitoring_id'],
        'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN HEALTH',
        'observed_successor_next_generation_ten_hash': 'a' * 64,
        'control_state': 'healthy',
        'audit_statement': 'Successor ten controls are stable.',
    })
    assert audit.status_code == 200
    assert audit.json()['audit']['healthy'] is True

    baseline = client.post('/auron/demo1/v21.414/baseline/certify', json={
        'actor': 'master-brano',
        'monitoring_id': monitoring['monitoring_id'],
        'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN RENEWED BASELINE',
        'observed_successor_next_generation_ten_hash': 'a' * 64,
        'control_state': 'healthy',
        'baseline_reference': 'BASELINE-414',
        'baseline_statement': 'Renewed successor ten baseline certified.',
    })
    assert baseline.status_code == 200
    assert baseline.json()['baseline']['baseline_state'] == 'successor-next-generation-ten-renewed-baseline-certified-active'
    assert baseline.json()['external_calls_made'] == 0


def test_hash_mismatch_fails_closed_and_opens_drift() -> None:
    client = build_client()
    monitoring = start_monitoring(client)
    audit = client.post('/auron/demo1/v21.414/health/audit', json={
        'actor': 'master-brano',
        'monitoring_id': monitoring['monitoring_id'],
        'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN HEALTH',
        'observed_successor_next_generation_ten_hash': 'c' * 64,
        'control_state': 'healthy',
        'audit_statement': 'Unexpected successor ten hash.',
    })
    assert audit.status_code == 200
    body = audit.json()
    assert body['audit']['healthy'] is False
    assert body['monitoring']['monitoring_state'] == 'successor-next-generation-ten-drift-detected'

    drift = client.post('/auron/demo1/v21.414/drift/open', json={
        'actor': 'master-brano',
        'monitoring_id': monitoring['monitoring_id'],
        'trigger_audit_id': body['audit']['audit_id'],
        'open_phrase': 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN DRIFT',
        'drift_reference': 'DRIFT-414',
        'drift_statement': 'Hash mismatch requires governed remediation.',
    })
    assert drift.status_code == 200
    assert drift.json()['drift']['drift_state'] == 'successor-next-generation-ten-drift-open'

    baseline = client.post('/auron/demo1/v21.414/baseline/certify', json={
        'actor': 'master-brano',
        'monitoring_id': monitoring['monitoring_id'],
        'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN RENEWED BASELINE',
        'observed_successor_next_generation_ten_hash': 'a' * 64,
        'control_state': 'healthy',
        'baseline_reference': 'BLOCKED-414',
        'baseline_statement': 'Must remain blocked while drift is open.',
    })
    assert baseline.status_code == 409


def test_command_center_available() -> None:
    response = build_client().get('/auron/demo1/v21.414/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION TEN MONITORING COMMAND CENTER' in response.text
    assert 'no outbound message' in response.text
