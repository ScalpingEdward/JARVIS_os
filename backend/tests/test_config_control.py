import os

import pytest
from pydantic import ValidationError

from app.config_control.models import ComponentConfigCreate, ComponentKind, ConfigState, SecretReference
from app.config_control.service import configuration_control_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    configuration_control_service.reset()


def test_rejects_plaintext_secret_values() -> None:
    with pytest.raises(ValidationError):
        ComponentConfigCreate(
            name="OpenAI",
            kind=ComponentKind.model_provider,
            settings={"api_key": "secret-value"},
        )


def test_missing_secret_marks_component_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    record = configuration_control_service.create(
        ComponentConfigCreate(
            name="OpenAI",
            kind=ComponentKind.model_provider,
            secret_references=[SecretReference(name="OPENAI_API_KEY")],
        )
    )
    assert record.state == ConfigState.degraded
    assert record.missing_secrets == ["OPENAI_API_KEY"]


def test_available_secret_marks_component_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "runtime-only")
    record = configuration_control_service.create(
        ComponentConfigCreate(
            name="Telegram",
            kind=ComponentKind.telegram,
            secret_references=[SecretReference(name="TELEGRAM_BOT_TOKEN")],
        )
    )
    assert record.state == ConfigState.ready
    assert record.missing_secrets == []
    assert configuration_control_service.status().plaintext_secrets_stored is False
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)


def test_disabled_component_is_not_ready() -> None:
    record = configuration_control_service.create(
        ComponentConfigCreate(name="MT5", kind=ComponentKind.mt5, enabled=False)
    )
    assert record.state == ConfigState.disabled
    assert configuration_control_service.status().automatic_order_execution is False
