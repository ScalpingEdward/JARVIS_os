import pytest
from pydantic import ValidationError

from app.localization.models import (
    LocaleMutation, LocaleProfileCreate, ProfileState, ResolveRequest,
    TextDirection, TranslationEntryCreate,
)
from app.localization.service import LocalizationService


def profile(locale: str = "de-DE") -> LocaleProfileCreate:
    return LocaleProfileCreate(
        workspace_id="workspace-1", owner_id="owner-1", profile_key="primary",
        locale=locale, language_name="Deutsch", region="Germany",
        timezone="Europe/Berlin", currency="EUR", fallback_locales=["en-US"],
    )


def test_profile_and_status_support_many_locales():
    service = LocalizationService()
    item = service.create_profile(profile())
    assert item.locale == "de-DE"
    assert service.status().supported_locale_count >= 60
    assert service.status().rtl_supported is True
    assert service.status().live_switch_supported is True


def test_translation_resolution_and_variables():
    service = LocalizationService()
    service.create_profile(profile())
    service.create_translation(TranslationEntryCreate(
        workspace_id="workspace-1", owner_id="owner-1", namespace="core",
        message_key="welcome", locale="de-DE", text="Willkommen, {name}!",
        placeholders=["name"], source_locale="en-US",
    ))
    result = service.resolve(ResolveRequest(
        workspace_id="workspace-1", locale="de-DE", namespace="core",
        message_key="welcome", variables={"name": "Brano"},
    ))
    assert result.found is True
    assert result.text == "Willkommen, Brano!"
    assert result.used_fallback is False


def test_fallback_chain_uses_english():
    service = LocalizationService()
    service.create_profile(profile("sk-SK"))
    service.create_translation(TranslationEntryCreate(
        workspace_id="workspace-1", owner_id="owner-1", namespace="core",
        message_key="status.ready", locale="en-US", text="System ready",
    ))
    result = service.resolve(ResolveRequest(
        workspace_id="workspace-1", locale="sk-SK", namespace="core",
        message_key="status.ready",
    ))
    assert result.found is True
    assert result.resolved_locale == "en-US"
    assert result.used_fallback is True


def test_missing_translation_is_explicit():
    result = LocalizationService().resolve(ResolveRequest(
        workspace_id="workspace-1", locale="de-DE", namespace="core",
        message_key="missing.key",
    ))
    assert result.found is False
    assert result.text is None
    assert "en-US" in result.fallback_chain


def test_rtl_profile_supported():
    item = LocalizationService().create_profile(LocaleProfileCreate(
        workspace_id="workspace-1", owner_id="owner-1", profile_key="arabic",
        locale="ar-SA", language_name="العربية", region="Saudi Arabia",
        timezone="Asia/Riyadh", currency="SAR", text_direction=TextDirection.RTL,
    ))
    assert item.text_direction == TextDirection.RTL


def test_owner_and_workspace_isolation():
    service = LocalizationService()
    item = service.create_profile(profile())
    assert service.get_profile(item.id, "other-workspace") is None
    assert service.set_profile_state(
        item.id, "workspace-1", LocaleMutation(requester_id="wrong-owner"), ProfileState.SUSPENDED,
    ) is None


def test_duplicate_translation_rejected():
    service = LocalizationService()
    payload = TranslationEntryCreate(
        workspace_id="workspace-1", owner_id="owner-1", namespace="core",
        message_key="hello", locale="de-DE", text="Hallo",
    )
    service.create_translation(payload)
    with pytest.raises(ValueError):
        service.create_translation(payload)


def test_safety_rejects_external_translation_and_html_rendering():
    with pytest.raises(ValidationError):
        LocaleProfileCreate.model_validate({**profile().model_dump(), "automatic_external_translation": True})
    with pytest.raises(ValidationError):
        ResolveRequest(
            workspace_id="workspace-1", locale="de-DE", namespace="core",
            message_key="welcome", render_html=True,
        )


def test_number_separators_must_differ():
    with pytest.raises(ValidationError):
        LocaleProfileCreate(
            workspace_id="workspace-1", owner_id="owner-1", profile_key="bad",
            locale="de-DE", language_name="Deutsch", region="Germany",
            timezone="Europe/Berlin", currency="EUR",
            number_decimal_separator=",", number_group_separator=",",
        )
