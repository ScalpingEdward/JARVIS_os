from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_nine_monitoring_v21_410 import (
    _monitoring_store,
    _resolution_store,
    reset_telegram_successor_next_generation_nine_monitoring_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_nine_recertification_v21_411 import (
    reset_telegram_successor_next_generation_nine_recertification_store,
    router,
)


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_nine_monitoring_store()
    reset_telegram_successor_next_generation_nine_recertification_store()


def seed_resolution() -> str:
    monitoring_id = 'monitoring-v21-410'
    resolution_id = 'resolution-v21-410'
    _monitoring_store['cert-v21-409'] = {
        'monitoring_id': monitoring_id,
        'monitoring_state': 'successor-next-generation-nine-drift-remediation-pending-validation',
        'active_successor_next_generation_nine_hash': 'a' * 64,
        'external_calls_made': 0,
    }
    _resolution_store['drift-v21-410'] = {
        'resolution_id': resolution_id,
        'monitoring_id': monitoring_id,
        'corrected_hash': 'a' * 64,
        'resolution_state': 'successor-next-generation-nine-drift-resolved',
        'integrity_hash': 'b' * 64,
        'immutable': True,
    }
    return resolution_id


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.411/remediation/validate' in paths
    assert '/auron/demo1/v21.411/succession/recertify' in paths
    assert '/auron/demo1/v21.411/baseline/renew' in paths
    assert '/auron/demo1/v21.411/status' in paths
    assert '/auron/demo1/v21.411/command-center' in paths


def test_safe_empty_status() -> None:
    response = build_client().get('/auron/demo1/v21.411/status')
    assert response.status_code == 200
    assert response.json()['external_calls_made'] == 0
    assert response.json()['validations'] == 0
    assert response.json()['recertifications'] == 0
    assert response.json()['renewed_baselines'] == 0


def test_validation_requires_explicit_phrase() -> None:
    resolution_id = seed_resolution()
    response = build_client().post('/auron/demo1/v21.411/remediation/validate', json={
        'actor': 'master-brano',
        'resolution_id': resolution_id,
        'validation_phrase': 'wrong phrase',
        'observed_successor_next_generation_nine_hash': 'a' * 64,
        'control_state': 'healthy',
        'validation_reference': 'VAL-411',
        'validation_statement': 'Stable remediation.',
    })
    assert response.status_code == 403


def test_full_recertification_and_baseline_flow() -> None:
    client = build_client()
    resolution_id = seed_resolution()
    validation = client.post('/auron/demo1/v21.411/remediation/validate', json={
        'actor': 'master-brano',
        'resolution_id': resolution_id,
        'validation_phrase': 'VALIDATE AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE REMEDIATION',
        'observed_successor_next_generation_nine_hash': 'a' * 64,
        'control_state': 'healthy',
        'validation_reference': 'VAL-411',
        'validation_statement': 'Stable remediation.',
    })
    assert validation.status_code == 200
    validation_id = validation.json()['validation']['validation_id']

    recertification = client.post('/auron/demo1/v21.411/succession/recertify', json={
        'actor': 'master-brano',
        'validation_id': validation_id,
        'recertification_phrase': 'RECERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE SUCCESSION',
        'recertification_reference': 'RECERT-411',
        'recertification_statement': 'Succession stable.',
    })
    assert recertification.status_code == 200
    recertification_id = recertification.json()['recertification']['recertification_id']

    baseline = client.post('/auron/demo1/v21.411/baseline/renew', json={
        'actor': 'master-brano',
        'recertification_id': recertification_id,
        'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE BASELINE',
        'baseline_reference': 'BASELINE-411',
        'baseline_statement': 'Renewed baseline active.',
    })
    assert baseline.status_code == 200
    body = baseline.json()
    assert body['baseline']['immutable'] is True
    assert body['monitoring']['monitoring_state'] == 'certified-successor-next-generation-nine-monitoring-active'
    assert body['external_calls_made'] == 0


def test_validation_fails_closed_on_hash_mismatch() -> None:
    resolution_id = seed_resolution()
    response = build_client().post('/auron/demo1/v21.411/remediation/validate', json={
        'actor': 'master-brano',
        'resolution_id': resolution_id,
        'validation_phrase': 'VALIDATE AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE REMEDIATION',
        'observed_successor_next_generation_nine_hash': 'c' * 64,
        'control_state': 'healthy',
        'validation_reference': 'VAL-411',
        'validation_statement': 'Mismatched remediation.',
    })
    assert response.status_code == 409
    assert 'observed_hash_matches' in response.text


def test_command_center_available() -> None:
    response = build_client().get('/auron/demo1/v21.411/command-center')
    assert response.status_code == 200
    assert 'AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE RECERTIFICATION COMMAND CENTER' in response.text
    assert 'no outbound message' in response.text
