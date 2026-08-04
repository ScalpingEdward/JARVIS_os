from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_eleven_continuity_v21_418 import (
    _renewal_store,
    reset_telegram_successor_next_generation_eleven_continuity_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_eleven_monitoring_v21_417 import (
    _monitor_store,
    reset_telegram_successor_next_generation_eleven_monitoring_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_twelve_restoration_v21_419 import (
    reset_telegram_successor_next_generation_twelve_restoration_store,
    router,
)


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_twelve_restoration_store()
    reset_telegram_successor_next_generation_eleven_continuity_store()
    reset_telegram_successor_next_generation_eleven_monitoring_store()


def seed_renewal() -> str:
    monitoring_id = 'monitor-v21-417'
    renewal_request_id = 'renewal-v21-418'
    _monitor_store['cert-v21-417'] = {
        'monitoring_id': monitoring_id,
        'monitoring_state': 'successor-next-generation-eleven-renewal-required',
        'integrity_hash': 'a' * 64,
        'immutable': True,
    }
    _renewal_store['expiry-v21-418'] = {
        'renewal_request_id': renewal_request_id,
        'renewal_state': 'successor-next-generation-eleven-renewal-requested',
        'monitoring_id': monitoring_id,
        'baseline_id': 'baseline-v21-417',
        'integrity_hash': 'b' * 64,
        'immutable': True,
    }
    return renewal_request_id


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.419/restoration/prepare' in paths
    assert '/auron/demo1/v21.419/activation/execute' in paths
    assert '/auron/demo1/v21.419/succession/certify' in paths
    assert '/auron/demo1/v21.419/status' in paths
    assert '/auron/demo1/v21.419/command-center' in paths


def test_safe_empty_status() -> None:
    response = build_client().get('/auron/demo1/v21.419/status')
    assert response.status_code == 200
    assert response.json() == {
        'restorations': 0,
        'activations': 0,
        'succession_certifications': 0,
        'external_calls_made': 0,
        'mode': 'successor-next-generation-twelve-restoration-controlled-activation-succession-governance',
    }


def test_restoration_requires_explicit_phrase() -> None:
    renewal_id = seed_renewal()
    response = build_client().post('/auron/demo1/v21.419/restoration/prepare', json={
        'actor': 'master-brano',
        'renewal_request_id': renewal_id,
        'restoration_phrase': 'wrong phrase',
        'proposed_successor_next_generation_twelve_hash': 'c' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'RESTORE-419',
        'restoration_statement': 'Prepare generation twelve.',
    })
    assert response.status_code == 403


def test_complete_restoration_activation_certification_flow() -> None:
    renewal_id = seed_renewal()
    client = build_client()
    restored = client.post('/auron/demo1/v21.419/restoration/prepare', json={
        'actor': 'master-brano',
        'renewal_request_id': renewal_id,
        'restoration_phrase': 'RESTORE AURON TELEGRAM SUCCESSOR NEXT GENERATION TWELVE',
        'proposed_successor_next_generation_twelve_hash': 'c' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'RESTORE-419',
        'restoration_statement': 'Prepare generation twelve.',
    })
    assert restored.status_code == 200
    restoration_id = restored.json()['restoration']['restoration_id']

    activated = client.post('/auron/demo1/v21.419/activation/execute', json={
        'actor': 'master-brano',
        'restoration_id': restoration_id,
        'activation_phrase': 'ACTIVATE AURON TELEGRAM SUCCESSOR NEXT GENERATION TWELVE',
        'observed_successor_next_generation_twelve_hash': 'c' * 64,
        'control_state': 'healthy',
        'activation_reference': 'ACTIVATE-419',
        'activation_statement': 'Activate generation twelve.',
    })
    assert activated.status_code == 200
    activation_id = activated.json()['activation']['activation_id']

    certified = client.post('/auron/demo1/v21.419/succession/certify', json={
        'actor': 'master-brano',
        'activation_id': activation_id,
        'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION TWELVE SUCCESSION',
        'certification_reference': 'CERTIFY-419',
        'certification_statement': 'Certify generation twelve.',
    })
    assert certified.status_code == 200
    assert certified.json()['certification']['certification_state'] == 'successor-next-generation-twelve-succession-certified-stable'
    assert certified.json()['monitoring']['monitoring_state'] == 'certified-successor-next-generation-twelve-monitoring-pending'
    assert certified.json()['external_calls_made'] == 0


def test_activation_hash_mismatch_fails_closed() -> None:
    renewal_id = seed_renewal()
    client = build_client()
    restored = client.post('/auron/demo1/v21.419/restoration/prepare', json={
        'actor': 'master-brano',
        'renewal_request_id': renewal_id,
        'restoration_phrase': 'RESTORE AURON TELEGRAM SUCCESSOR NEXT GENERATION TWELVE',
        'proposed_successor_next_generation_twelve_hash': 'c' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'RESTORE-419',
        'restoration_statement': 'Prepare generation twelve.',
    })
    response = client.post('/auron/demo1/v21.419/activation/execute', json={
        'actor': 'master-brano',
        'restoration_id': restored.json()['restoration']['restoration_id'],
        'activation_phrase': 'ACTIVATE AURON TELEGRAM SUCCESSOR NEXT GENERATION TWELVE',
        'observed_successor_next_generation_twelve_hash': 'd' * 64,
        'control_state': 'healthy',
        'activation_reference': 'ACTIVATE-419',
        'activation_statement': 'Mismatched activation.',
    })
    assert response.status_code == 409
    assert 'hash_matches' in response.json()['detail']['blockers']


def test_command_center_available() -> None:
    response = build_client().get('/auron/demo1/v21.419/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION TWELVE RESTORATION COMMAND CENTER' in response.text
    assert 'no outbound message' in response.text
