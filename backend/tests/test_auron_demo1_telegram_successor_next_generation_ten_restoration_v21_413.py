from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_ten_restoration_v21_413 import (
    reset_telegram_successor_next_generation_ten_restoration_store,
    router,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_nine_continuity_v21_412 import (
    _renewal_request_store,
    reset_telegram_successor_next_generation_nine_continuity_store,
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
    reset_telegram_successor_next_generation_ten_restoration_store()
    reset_telegram_successor_next_generation_nine_continuity_store()
    reset_telegram_successor_next_generation_nine_monitoring_store()


def seed_renewal() -> str:
    monitoring_id = 'monitoring-v21-413'
    _monitoring_store['cert-v21-409'] = {
        'monitoring_id': monitoring_id,
        'monitoring_state': 'successor-next-generation-nine-renewal-required',
        'immutable': True,
        'integrity_hash': 'a' * 64,
    }
    renewal_id = 'renewal-v21-413'
    _renewal_request_store['expiry-v21-412'] = {
        'renewal_request_id': renewal_id,
        'renewal_state': 'successor-next-generation-nine-renewal-requested',
        'baseline_id': 'baseline-v21-411',
        'monitoring_id': monitoring_id,
        'immutable': True,
        'integrity_hash': 'b' * 64,
    }
    return renewal_id


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.413/restoration/prepare' in paths
    assert '/auron/demo1/v21.413/activation/execute' in paths
    assert '/auron/demo1/v21.413/succession/certify' in paths
    assert '/auron/demo1/v21.413/status' in paths
    assert '/auron/demo1/v21.413/command-center' in paths


def test_safe_empty_status() -> None:
    response = build_client().get('/auron/demo1/v21.413/status')
    assert response.status_code == 200
    assert response.json() == {
        'restorations': 0,
        'activations': 0,
        'succession_certifications': 0,
        'external_calls_made': 0,
        'mode': 'successor-next-generation-ten-restoration-controlled-activation-succession-governance',
    }


def test_restoration_requires_explicit_phrase() -> None:
    renewal_id = seed_renewal()
    response = build_client().post('/auron/demo1/v21.413/restoration/prepare', json={
        'actor': 'master-brano',
        'renewal_request_id': renewal_id,
        'restoration_phrase': 'wrong phrase',
        'proposed_successor_next_generation_ten_hash': 'c' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'REST-413',
        'restoration_statement': 'Prepare generation ten.',
    })
    assert response.status_code == 403


def test_full_restoration_activation_and_certification_flow() -> None:
    renewal_id = seed_renewal()
    client = build_client()
    restored = client.post('/auron/demo1/v21.413/restoration/prepare', json={
        'actor': 'master-brano',
        'renewal_request_id': renewal_id,
        'restoration_phrase': 'RESTORE AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN',
        'proposed_successor_next_generation_ten_hash': 'c' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'REST-413',
        'restoration_statement': 'Prepare generation ten.',
    })
    assert restored.status_code == 200
    restoration_id = restored.json()['restoration']['restoration_id']

    activated = client.post('/auron/demo1/v21.413/activation/execute', json={
        'actor': 'master-brano',
        'restoration_id': restoration_id,
        'activation_phrase': 'ACTIVATE AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN',
        'observed_successor_next_generation_ten_hash': 'c' * 64,
        'control_state': 'healthy',
        'activation_reference': 'ACT-413',
        'activation_statement': 'Activate generation ten.',
    })
    assert activated.status_code == 200
    activation_id = activated.json()['activation']['activation_id']

    certified = client.post('/auron/demo1/v21.413/succession/certify', json={
        'actor': 'master-brano',
        'activation_id': activation_id,
        'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN SUCCESSION',
        'certification_reference': 'CERT-413',
        'certification_statement': 'Certify stable succession.',
    })
    assert certified.status_code == 200
    assert certified.json()['certification']['certification_state'] == 'successor-next-generation-ten-succession-certified-stable'
    assert certified.json()['monitoring']['monitoring_state'] == 'certified-successor-next-generation-ten-monitoring-pending'
    assert certified.json()['external_calls_made'] == 0


def test_hash_mismatch_fails_closed() -> None:
    renewal_id = seed_renewal()
    client = build_client()
    restored = client.post('/auron/demo1/v21.413/restoration/prepare', json={
        'actor': 'master-brano',
        'renewal_request_id': renewal_id,
        'restoration_phrase': 'RESTORE AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN',
        'proposed_successor_next_generation_ten_hash': 'c' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'REST-413',
        'restoration_statement': 'Prepare generation ten.',
    })
    restoration_id = restored.json()['restoration']['restoration_id']
    response = client.post('/auron/demo1/v21.413/activation/execute', json={
        'actor': 'master-brano',
        'restoration_id': restoration_id,
        'activation_phrase': 'ACTIVATE AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN',
        'observed_successor_next_generation_ten_hash': 'd' * 64,
        'control_state': 'healthy',
        'activation_reference': 'ACT-413',
        'activation_statement': 'Mismatched activation.',
    })
    assert response.status_code == 409
    assert 'hash_matches' in response.json()['detail']['blockers']


def test_command_center_available() -> None:
    response = build_client().get('/auron/demo1/v21.413/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION TEN RESTORATION COMMAND CENTER' in response.text
    assert 'no outbound message' in response.text
