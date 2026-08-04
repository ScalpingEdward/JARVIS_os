from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_eleven_restoration_v21_416 import (
    reset_telegram_successor_next_generation_eleven_restoration_store,
    router,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_ten_continuity_v21_415 import (
    _renewal_store,
    reset_telegram_successor_next_generation_ten_continuity_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_ten_monitoring_v21_414 import (
    _monitor_store,
    reset_telegram_successor_next_generation_ten_monitoring_store,
)


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_eleven_restoration_store()
    reset_telegram_successor_next_generation_ten_continuity_store()
    reset_telegram_successor_next_generation_ten_monitoring_store()


def seed_renewal() -> str:
    monitoring_id = 'monitor-v21-414'
    renewal_id = 'renewal-v21-415'
    _monitor_store['cert-v21-413'] = {
        'monitoring_id': monitoring_id,
        'monitoring_state': 'successor-next-generation-ten-renewal-required',
    }
    _renewal_store['expiry-v21-415'] = {
        'renewal_request_id': renewal_id,
        'renewal_state': 'successor-next-generation-ten-renewal-requested',
        'monitoring_id': monitoring_id,
        'baseline_id': 'baseline-v21-414',
        'integrity_hash': 'a' * 64,
        'immutable': True,
    }
    return renewal_id


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.416/restoration/prepare' in paths
    assert '/auron/demo1/v21.416/activation/execute' in paths
    assert '/auron/demo1/v21.416/succession/certify' in paths
    assert '/auron/demo1/v21.416/status' in paths
    assert '/auron/demo1/v21.416/command-center' in paths


def test_safe_empty_status() -> None:
    response = build_client().get('/auron/demo1/v21.416/status')
    assert response.status_code == 200
    assert response.json()['external_calls_made'] == 0
    assert response.json()['restorations'] == 0


def test_restoration_requires_explicit_phrase() -> None:
    renewal_id = seed_renewal()
    response = build_client().post('/auron/demo1/v21.416/restoration/prepare', json={
        'actor': 'master-brano',
        'renewal_request_id': renewal_id,
        'restoration_phrase': 'wrong phrase',
        'proposed_successor_next_generation_eleven_hash': 'b' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'REST-416',
        'restoration_statement': 'Prepare generation eleven.',
    })
    assert response.status_code == 403


def test_complete_restoration_activation_certification_flow() -> None:
    renewal_id = seed_renewal()
    client = build_client()
    restored = client.post('/auron/demo1/v21.416/restoration/prepare', json={
        'actor': 'master-brano',
        'renewal_request_id': renewal_id,
        'restoration_phrase': 'RESTORE AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN',
        'proposed_successor_next_generation_eleven_hash': 'b' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'REST-416',
        'restoration_statement': 'Prepare generation eleven.',
    })
    assert restored.status_code == 200
    restoration_id = restored.json()['restoration']['restoration_id']

    activated = client.post('/auron/demo1/v21.416/activation/execute', json={
        'actor': 'master-brano',
        'restoration_id': restoration_id,
        'activation_phrase': 'ACTIVATE AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN',
        'observed_successor_next_generation_eleven_hash': 'b' * 64,
        'control_state': 'healthy',
        'activation_reference': 'ACT-416',
        'activation_statement': 'Controlled activation.',
    })
    assert activated.status_code == 200
    activation_id = activated.json()['activation']['activation_id']

    certified = client.post('/auron/demo1/v21.416/succession/certify', json={
        'actor': 'master-brano',
        'activation_id': activation_id,
        'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN SUCCESSION',
        'certification_reference': 'CERT-416',
        'certification_statement': 'Stable succession certified.',
    })
    assert certified.status_code == 200
    assert certified.json()['certification']['certification_state'] == 'successor-next-generation-eleven-succession-certified-stable'
    assert certified.json()['external_calls_made'] == 0


def test_hash_mismatch_fails_closed() -> None:
    renewal_id = seed_renewal()
    client = build_client()
    restored = client.post('/auron/demo1/v21.416/restoration/prepare', json={
        'actor': 'master-brano',
        'renewal_request_id': renewal_id,
        'restoration_phrase': 'RESTORE AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN',
        'proposed_successor_next_generation_eleven_hash': 'b' * 64,
        'control_state': 'healthy',
        'restoration_reference': 'REST-416',
        'restoration_statement': 'Prepare generation eleven.',
    })
    restoration_id = restored.json()['restoration']['restoration_id']
    response = client.post('/auron/demo1/v21.416/activation/execute', json={
        'actor': 'master-brano',
        'restoration_id': restoration_id,
        'activation_phrase': 'ACTIVATE AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN',
        'observed_successor_next_generation_eleven_hash': 'c' * 64,
        'control_state': 'healthy',
        'activation_reference': 'ACT-416',
        'activation_statement': 'Mismatched activation.',
    })
    assert response.status_code == 409
    assert 'hash_matches' in response.json()['detail']['blockers']


def test_command_center_available() -> None:
    response = build_client().get('/auron/demo1/v21.416/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION ELEVEN COMMAND CENTER' in response.text
    assert 'no outbound message' in response.text
