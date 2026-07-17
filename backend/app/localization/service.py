from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord, LocaleMutation, LocaleProfileCreate, LocaleProfileRecord,
    LocalizationStatus, ProfileState, ResolveRecord, ResolveRequest,
    TranslationEntryCreate, TranslationEntryRecord, TranslationState,
)


COMMON_LOCALES = {
    "de-DE", "en-US", "en-GB", "sk-SK", "cs-CZ", "pl-PL", "fr-FR",
    "es-ES", "it-IT", "pt-PT", "pt-BR", "nl-NL", "sv-SE", "da-DK",
    "no-NO", "fi-FI", "et-EE", "lv-LV", "lt-LT", "hu-HU", "ro-RO",
    "bg-BG", "hr-HR", "sl-SI", "sr-RS", "uk-UA", "ru-RU", "tr-TR",
    "el-GR", "ar-SA", "he-IL", "fa-IR", "hi-IN", "bn-BD", "ur-PK",
    "th-TH", "vi-VN", "id-ID", "ms-MY", "zh-CN", "zh-TW", "ja-JP",
    "ko-KR", "fil-PH", "sw-KE", "af-ZA", "is-IS", "ca-ES", "eu-ES",
    "gl-ES", "ga-IE", "cy-GB", "mt-MT", "mk-MK", "sq-AL", "ka-GE",
    "hy-AM", "az-AZ", "kk-KZ", "uz-UZ", "mn-MN", "ne-NP", "si-LK",
    "ta-IN", "te-IN", "mr-IN", "gu-IN", "kn-IN", "ml-IN", "pa-IN",
}


class LocalizationService:
    def __init__(self) -> None:
        self.profiles: dict[UUID, LocaleProfileRecord] = {}
        self.translations: dict[UUID, TranslationEntryRecord] = {}
        self.resolutions: list[ResolveRecord] = []
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, **details: object) -> None:
        self.audit.append(AuditRecord(
            workspace_id=workspace_id, action=action, entity_type=entity_type,
            entity_id=entity_id, actor_id=actor_id, details=details,
        ))

    def status(self) -> LocalizationStatus:
        dynamic = {item.locale for item in self.profiles.values()} | {item.locale for item in self.translations.values()}
        return LocalizationStatus(
            supported_locale_count=len(COMMON_LOCALES | dynamic),
            profiles=len(self.profiles), translations=len(self.translations),
            resolutions=len(self.resolutions),
        )

    def create_profile(self, payload: LocaleProfileCreate) -> LocaleProfileRecord:
        for item in self.profiles.values():
            if item.workspace_id == payload.workspace_id and item.profile_key == payload.profile_key:
                raise ValueError("profile key already exists in workspace")
        record = LocaleProfileRecord(**payload.model_dump())
        self.profiles[record.id] = record
        self._audit(record.workspace_id, "profile.created", "locale_profile", record.id, record.owner_id, locale=record.locale)
        return record

    def list_profiles(self, workspace_id: str) -> list[LocaleProfileRecord]:
        return [item for item in self.profiles.values() if item.workspace_id == workspace_id]

    def get_profile(self, profile_id: UUID, workspace_id: str) -> LocaleProfileRecord | None:
        item = self.profiles.get(profile_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_profile_state(self, profile_id: UUID, workspace_id: str, payload: LocaleMutation, state: ProfileState) -> LocaleProfileRecord | None:
        item = self.get_profile(profile_id, workspace_id)
        if not item or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"profile.{state.value}", "locale_profile", item.id, payload.requester_id, reason=payload.reason)
        return item

    def create_translation(self, payload: TranslationEntryCreate) -> TranslationEntryRecord:
        for item in self.translations.values():
            if (item.workspace_id, item.namespace, item.message_key, item.locale, item.state) == (
                payload.workspace_id, payload.namespace, payload.message_key, payload.locale, TranslationState.ACTIVE,
            ):
                raise ValueError("active translation already exists for locale and key")
        record = TranslationEntryRecord(**payload.model_dump())
        self.translations[record.id] = record
        self._audit(record.workspace_id, "translation.created", "translation", record.id, record.owner_id, locale=record.locale, key=record.message_key)
        return record

    def list_translations(self, workspace_id: str, locale: str | None = None, namespace: str | None = None) -> list[TranslationEntryRecord]:
        return [item for item in self.translations.values() if item.workspace_id == workspace_id and (locale is None or item.locale == locale) and (namespace is None or item.namespace == namespace)]

    def retire_translation(self, translation_id: UUID, workspace_id: str, payload: LocaleMutation) -> TranslationEntryRecord | None:
        item = self.translations.get(translation_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.state = TranslationState.RETIRED
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "translation.retired", "translation", item.id, payload.requester_id, reason=payload.reason)
        return item

    def resolve(self, payload: ResolveRequest) -> ResolveRecord:
        profile = next((p for p in self.profiles.values() if p.workspace_id == payload.workspace_id and p.locale == payload.locale and p.state == ProfileState.ACTIVE), None)
        chain: list[str] = []
        for locale in [payload.locale, *payload.fallback_locales, *(profile.fallback_locales if profile else []), "en-US"]:
            if locale not in chain:
                chain.append(locale)
        selected = None
        for locale in chain:
            selected = next((item for item in self.translations.values() if item.workspace_id == payload.workspace_id and item.locale == locale and item.namespace == payload.namespace and item.message_key == payload.message_key and item.state == TranslationState.ACTIVE), None)
            if selected:
                break
        record = ResolveRecord(
            workspace_id=payload.workspace_id, requested_locale=payload.locale,
            resolved_locale=selected.locale if selected else None,
            namespace=payload.namespace, message_key=payload.message_key,
            found=selected is not None, used_fallback=bool(selected and selected.locale != payload.locale),
            fallback_chain=chain,
        )
        if selected:
            text = selected.text
            missing: list[str] = []
            for placeholder in selected.placeholders:
                token = "{" + placeholder + "}"
                if placeholder in payload.variables:
                    text = text.replace(token, str(payload.variables[placeholder]))
                else:
                    missing.append(placeholder)
            record.text = text
            record.missing_placeholders = missing
        self.resolutions.append(record)
        self._audit(payload.workspace_id, "translation.resolved", "resolution", record.id, "system", found=record.found, locale=record.resolved_locale)
        return record

    def list_resolutions(self, workspace_id: str) -> list[ResolveRecord]:
        return [item for item in self.resolutions if item.workspace_id == workspace_id]

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit if item.workspace_id == workspace_id]


localization_service = LocalizationService()
