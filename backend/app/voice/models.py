from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class VoiceIntent(StrEnum):
    status = "status"
    today = "today"
    approvals = "approvals"
    pause = "pause"
    resume = "resume"
    approve = "approve"
    reject = "reject"
    confirm = "confirm"
    cancel = "cancel"
    unknown = "unknown"


class VoiceSettings(BaseModel):
    assistant_name: str = Field(default="PHOENIX", min_length=2, max_length=40)
    wake_name: str = Field(default="phoenix", min_length=2, max_length=40)
    language: str = Field(default="de-DE", min_length=2, max_length=20)
    speech_to_text_provider: str = Field(default="provider-not-configured", max_length=80)
    text_to_speech_provider: str = Field(default="provider-not-configured", max_length=80)
    require_wake_name: bool = True
    critical_confirmation_required: bool = True


class VoiceTranscriptRequest(BaseModel):
    telegram_user_id: int
    chat_id: int
    transcript: str = Field(min_length=1, max_length=4000)


class TelegramVoiceRequest(BaseModel):
    telegram_user_id: int
    chat_id: int
    file_id: str = Field(min_length=1, max_length=500)
    mime_type: str = Field(default="audio/ogg", max_length=100)
    duration_seconds: int = Field(ge=1, le=600)
    transcript: str | None = Field(default=None, max_length=4000)


class VoiceConfirmation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: int
    intent: VoiceIntent
    argument: str | None = None


class VoiceReply(BaseModel):
    ok: bool
    assistant_name: str
    text: str
    intent: VoiceIntent
    requires_confirmation: bool = False
    confirmation_id: UUID | None = None
    speak_text: str | None = None
    sensitive_data_redacted: bool = True


class VoiceStatus(BaseModel):
    settings: VoiceSettings
    pending_confirmations: int
    telegram_voice_supported: bool = True
    raw_audio_stored: bool = False
    automatic_merge: bool = False
