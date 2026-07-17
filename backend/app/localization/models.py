from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class TextDirection(str, Enum):
    LTR = "ltr"
    RTL = "rtl"


class ProfileState(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class TranslationState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class LocaleProfileCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    profile_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    locale: str = Field(min_length=2, max_length=35, pattern=r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
    language_name: str = Field(min_length=1, max_length=120)
    region: str = Field(min_length=2, max_length=80)
    timezone: str = Field(min_length=1, max_length=120)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    date_format: str = Field(default="yyyy-MM-dd", min_length=1, max_length=80)
    time_format: str = Field(default="HH:mm", min_length=1, max_length=80)
    number_decimal_separator: str = Field(default=".", min_length=1, max_length=1)
    number_group_separator: str = Field(default=",", min_length=1, max_length=1)
    text_direction: TextDirection = TextDirection.LTR
    fallback_locales: list[str] = Field(default_factory=lambda: ["en-US"], max_length=20)
    ai_response_locale: str | None = Field(default=None, max_length=35)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_external_translation: bool = False
    execute_external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "LocaleProfileCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_external_translation:
            raise ValueError("automatic external translation is disabled in v9.3")
        if self.execute_external_action:
            raise ValueError("localization never executes external actions")
        if self.number_decimal_separator == self.number_group_separator:
            raise ValueError("decimal and group separators must differ")
        return self


class LocaleProfileRecord(LocaleProfileCreate):
    id: UUID = Field(default_factory=uuid4)
    state: ProfileState = ProfileState.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TranslationEntryCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    namespace: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    message_key: str = Field(min_length=1, max_length=240, pattern=r"^[a-z0-9_.-]+$")
    locale: str = Field(min_length=2, max_length=35)
    text: str = Field(min_length=1, max_length=10000)
    placeholders: list[str] = Field(default_factory=list, max_length=100)
    source_locale: str = Field(default="en-US", min_length=2, max_length=35)
    human_approved: bool = True
    machine_generated: bool = False
    publish_external: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "TranslationEntryCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.publish_external:
            raise ValueError("external publication is disabled")
        return self


class TranslationEntryRecord(TranslationEntryCreate):
    id: UUID = Field(default_factory=uuid4)
    state: TranslationState = TranslationState.ACTIVE
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LocaleMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=2000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "LocaleMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class ResolveRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    locale: str = Field(min_length=2, max_length=35)
    namespace: str = Field(min_length=1, max_length=160)
    message_key: str = Field(min_length=1, max_length=240)
    variables: dict[str, str | int | float] = Field(default_factory=dict)
    fallback_locales: list[str] = Field(default_factory=list, max_length=20)
    render_html: bool = False

    @model_validator(mode="after")
    def safe_rendering(self) -> "ResolveRequest":
        if self.render_html:
            raise ValueError("HTML rendering is disabled; localized output is plain text")
        return self


class ResolveRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    requested_locale: str
    resolved_locale: str | None = None
    namespace: str
    message_key: str
    text: str | None = None
    found: bool = False
    used_fallback: bool = False
    fallback_chain: list[str] = Field(default_factory=list)
    missing_placeholders: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    entity_type: str
    entity_id: UUID | None = None
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LocalizationStatus(BaseModel):
    version: str = "9.3"
    supported_locale_count: int
    profiles: int
    translations: int
    resolutions: int
    rtl_supported: bool = True
    live_switch_supported: bool = True
    external_translation_enabled: bool = False
    automatic_publication_enabled: bool = False
    executes_actions: bool = False
