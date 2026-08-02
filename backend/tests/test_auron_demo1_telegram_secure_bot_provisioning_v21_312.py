from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_secure_bot_provisioning_v21_312 as provisioning
from app.main import app


def setup_function() -> None:
    provisioning.reset_telegram_secure_bot_provisioning_store()


def test_valid_environment_is_accepted(monkeypatch) -> None:
    monkeypatch.setenv('TELEGRAM_RUNTIME_WORKER_ENABLED', 'true')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', '123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcd_1234')
    result = provisioning.validate_provisioning(
        provisioning.TelegramBotProvisioningValidationRequest(actor='brano', expected_bot_id='123456789')
    )
    assert result['state'] == 'telegram-bot-provisioning-validated'
    assert result['validation']['runtime_ready'] is True
    assert result['validation']['bot_token_persisted'] is False
    assert 'TELEGRAM_BOT_TOKEN' not in str(result)
    assert result['external_calls_made'] == 0


def test_invalid_token_is_blocked(monkeypatch) -> None:
    monkeypatch.setenv('TELEGRAM_RUNTIME_WORKER_ENABLED', 'true')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'invalid')
    result = provisioning.validate_provisioning(
        provisioning.TelegramBotProvisioningValidationRequest(actor='brano')
    )
    assert result['state'] == 'telegram-bot-provisioning-blocked'
    assert 'token_format_valid' in result['blockers']


def test_disabled_worker_is_blocked(monkeypatch) -> None:
    monkeypatch.setenv('TELEGRAM_RUNTIME_WORKER_ENABLED', 'false')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', '123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcd_1234')
    result = provisioning.validate_provisioning(
        provisioning.TelegramBotProvisioningValidationRequest(actor='brano')
    )
    assert 'worker_enabled' in result['blockers']


def test_validation_is_idempotent(monkeypatch) -> None:
    monkeypatch.setenv('TELEGRAM_RUNTIME_WORKER_ENABLED', 'true')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', '123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcd_1234')
    payload = provisioning.TelegramBotProvisioningValidationRequest(actor='brano')
    first = provisioning.validate_provisioning(payload)
    replay = provisioning.validate_provisioning(payload)
    assert replay['idempotent_replay'] is True
    assert replay['validation']['token_fingerprint'] == first['validation']['token_fingerprint']


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.312/command-center')
    assert response.status_code == 200
    assert 'v21.312' in response.text
    assert 'AURON TELEGRAM SECURE BOT PROVISIONING COMMAND CENTER' in response.text
