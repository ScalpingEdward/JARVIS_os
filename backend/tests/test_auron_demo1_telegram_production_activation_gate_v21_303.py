from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_gateway_runtime_v21_291 as gateway
from app.api.routes import auron_demo1_telegram_mobile_conversation_bridge_v21_290 as bridge
from app.api.routes import auron_demo1_telegram_production_activation_gate_v21_303 as gate
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.main import app


def setup_function() -> None:
    bridge.reset_telegram_bridge_store()
    gateway.reset_telegram_gateway_runtime_store()
    provider.reset_telegram_provider_registration_store()
    gate.reset_telegram_production_activation_gate_store()


def _ready_chain() -> None:
    bridge.bind_telegram_chat(bridge.TelegramBindRequest(
        actor='brano', telegram_chat_id='1001', telegram_user_id='2001',
        operator_id='brano', workspace_id='master', pairing_code_verified=True,
    ))
    gateway.configure_telegram_runtime(gateway.TelegramRuntimeConfigureRequest(
        actor='brano', bot_token='1234567890:abcdefghijklmnopqrstuvwxyz',
        webhook_base_url='https://auron.example.com', webhook_secret='telegram-secret-303',
        mode='webhook', enabled=True,
    ))
    provider.register_telegram_provider(provider.TelegramProviderRegisterRequest(
        actor='brano', webhook_registration_confirmed=True,
        provider_identity_verified=True, dry_run=True,
    ))


def _payload(**overrides):
    values = {
        'actor': 'brano',
        'approval_phrase': 'ACTIVATE AURON TELEGRAM PRODUCTION',
        'runtime_credentials_available': True,
        'webhook_endpoint_publicly_reachable': True,
        'tls_verified': True,
        'operator_chat_verified': True,
        'enable_live_transport': False,
    }
    values.update(overrides)
    return gate.TelegramProductionActivationRequest(**values)


def test_ready_transport_is_authorized_without_external_call() -> None:
    _ready_chain()
    result = gate.evaluate_telegram_production_activation(_payload())
    assert result['state'] == 'telegram-production-transport-authorized'
    assert result['activation']['production_transport_authorized'] is True
    assert result['activation']['activation_state'] == 'authorized-not-executed'
    assert result['activation']['live_transport_enabled'] is False
    assert result['telegram_api_calls_made'] == 0
    assert result['outbound_messages_sent'] == 0
    assert result['external_calls_made'] == 0


def test_missing_operator_approval_blocks_activation() -> None:
    _ready_chain()
    result = gate.evaluate_telegram_production_activation(_payload(approval_phrase='wrong phrase'))
    assert result['state'] == 'telegram-production-activation-blocked'
    assert 'explicit_operator_approval' in result['activation']['blockers']
    assert result['activation']['production_transport_authorized'] is False


def test_missing_runtime_readiness_blocks_activation() -> None:
    result = gate.evaluate_telegram_production_activation(_payload())
    assert result['state'] == 'telegram-production-activation-blocked'
    assert 'runtime_present' in result['activation']['blockers']
    assert 'provider_present' in result['activation']['blockers']


def test_activation_evaluation_is_idempotent() -> None:
    _ready_chain()
    payload = _payload()
    first = gate.evaluate_telegram_production_activation(payload)
    replay = gate.evaluate_telegram_production_activation(payload)
    assert replay['idempotent_replay'] is True
    assert replay['activation']['activation_id'] == first['activation']['activation_id']


def test_live_transport_execution_is_blocked() -> None:
    _ready_chain()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.303/evaluate', json={
        **_payload().model_dump(),
        'enable_live_transport': True,
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.303/command-center')
    assert response.status_code == 200
    assert 'v21.303' in response.text
    assert 'AURON TELEGRAM PRODUCTION ACTIVATION GATE COMMAND CENTER' in response.text
