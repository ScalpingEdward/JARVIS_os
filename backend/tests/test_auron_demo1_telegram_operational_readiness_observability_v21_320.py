import os

from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import auron_demo1_telegram_operational_readiness_observability_v21_320 as readiness
from app.api.routes import auron_demo1_telegram_gateway_runtime_v21_291 as runtime
from app.api.routes import auron_demo1_telegram_mobile_conversation_bridge_v21_290 as bridge
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.api.routes import auron_demo1_telegram_production_activation_gate_v21_303 as activation
from app.api.routes import auron_demo1_telegram_secure_bot_provisioning_v21_312 as provisioning


def setup_function() -> None:
    readiness.reset_telegram_operational_readiness_observability_store()
    runtime._runtime_store.clear()
    bridge._binding_store.clear()
    provider._provider_store.clear()
    activation._activation_store.clear()
    provisioning._validation_store.clear()
    os.environ['TELEGRAM_RUNTIME_WORKER_ENABLED'] = 'true'
    os.environ['TELEGRAM_BOT_TOKEN'] = '123456789:' + ('a' * 35)
    os.environ['TELEGRAM_WEBHOOK_SECRET'] = 'secret-320'

    runtime._runtime_store['runtime-320'] = {
        'runtime_id': 'runtime-320',
        'enabled': True,
        'active': True,
        'mode': 'webhook',
    }
    provider._provider_store['provider-320'] = {
        'provider_id': 'provider-320',
        'runtime_id': 'runtime-320',
        'provider_ready': True,
        'active': True,
    }
    activation._activation_store['activation-320'] = {
        'activation_id': 'activation-320',
        'provider_id': 'provider-320',
        'runtime_id': 'runtime-320',
        'production_transport_authorized': True,
        'active': True,
    }
    bridge._binding_store['1001'] = {
        'binding_id': 'binding-320',
        'telegram_chat_id': '1001',
        'telegram_user_id': '2002',
        'operator_id': 'brano',
        'workspace_id': 'jarvis-os',
        'active': True,
    }
    provisioning._validation_store['fingerprint-320'] = {
        'token_fingerprint': 'fingerprint-320',
        'bot_id': '123456789',
        'runtime_ready': True,
    }


def teardown_function() -> None:
    os.environ.pop('TELEGRAM_RUNTIME_WORKER_ENABLED', None)
    os.environ.pop('TELEGRAM_BOT_TOKEN', None)
    os.environ.pop('TELEGRAM_WEBHOOK_SECRET', None)


def _readiness_payload() -> dict:
    return {
        'actor': 'brano',
        'public_webhook_reachable': True,
        'tls_verified': True,
        'runtime_network_egress_available': True,
    }


def test_operational_readiness_passes() -> None:
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.320/evaluate', json=_readiness_payload())
    assert response.status_code == 200
    body = response.json()
    assert body['state'] == 'telegram-operationally-ready'
    assert body['readiness']['operationally_ready'] is True
    assert body['readiness']['blockers'] == []
    assert body['external_calls_made'] == 0


def test_missing_webhook_secret_blocks_readiness() -> None:
    os.environ.pop('TELEGRAM_WEBHOOK_SECRET')
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.320/evaluate', json=_readiness_payload())
    assert response.status_code == 200
    body = response.json()
    assert body['state'] == 'telegram-operational-readiness-blocked'
    assert 'webhook_secret_loaded' in body['readiness']['blockers']


def test_phone_validation_run_is_prepared_and_idempotent() -> None:
    client = TestClient(app)
    assert client.post('/auron/demo1/v21.320/evaluate', json=_readiness_payload()).status_code == 200
    payload = {
        'actor': 'brano',
        'telegram_chat_id': '1001',
        'validation_phrase': 'START ONE AURON TELEGRAM PHONE VALIDATION RUN',
        'test_message': 'Hallo AURON v21.320',
        'execute_external_actions': False,
    }
    first = client.post('/auron/demo1/v21.320/phone-validation/start', json=payload)
    replay = client.post('/auron/demo1/v21.320/phone-validation/start', json=payload)
    assert first.status_code == 200
    assert first.json()['state'] == 'telegram-phone-validation-run-prepared'
    assert replay.json()['idempotent_replay'] is True
    assert replay.json()['validation_run']['validation_run_id'] == first.json()['validation_run']['validation_run_id']


def test_phone_validation_requires_readiness() -> None:
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.320/phone-validation/start', json={
        'actor': 'brano',
        'telegram_chat_id': '1001',
        'validation_phrase': 'START ONE AURON TELEGRAM PHONE VALIDATION RUN',
        'test_message': 'Hallo AURON',
    })
    assert response.status_code == 409


def test_direct_external_execution_is_rejected() -> None:
    client = TestClient(app)
    assert client.post('/auron/demo1/v21.320/evaluate', json=_readiness_payload()).status_code == 200
    response = client.post('/auron/demo1/v21.320/phone-validation/start', json={
        'actor': 'brano',
        'telegram_chat_id': '1001',
        'validation_phrase': 'START ONE AURON TELEGRAM PHONE VALIDATION RUN',
        'test_message': 'Hallo AURON',
        'execute_external_actions': True,
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.320/command-center')
    assert response.status_code == 200
    assert 'v21.320' in response.text
    assert 'AURON TELEGRAM OPERATIONAL READINESS OBSERVABILITY COMMAND CENTER' in response.text
