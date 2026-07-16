from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class VoiceIntent(StrEnum):
    status = "status"
    today = "today"
    approvals = "approvals"
    market = "market"
    briefing = "briefing"
    pause = "pause"
    resume = "resume"
    approve = "approve"
    reject = "reject"
    confirm = "confirm"
    cancel = "cancel"
    wake = "wake"
    unknown = "unknown"


class VoiceSettings(BaseModel):
    assistant_name: str = Field(default="PHOENIX", min_length=2, max_length=40)
    wake_name: str = Field(default="phoenix", min_length=2, max_length=40)
    owner_salutation: str = Field(default="MASTER Brano", min_length=2, max_length=80)
    wake_reply: str = Field(default="Yes, MASTER Brano?", min_length=2, max_length=160)
    language: str = Field(default="de-DE", min_length=2, max_length=20)
    speech_to_text_provider: str = Field(default="browser-web-speech", max_length=80)
    text_to_speech_provider: str = Field(default="browser-speech-synthesis", max_length=80)
    require_wake_name: bool = True
    critical_confirmation_required: bool = True
    conversation_timeout_seconds: int = Field(default=45, ge=5, le=600)


class VoiceTranscriptRequest(BaseModel):
    telegram_user_id: int = 0
    chat_id: int = 0
    transcript: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(default="browser", min_length=1, max_length=120)
    source: str = Field(default="browser", max_length=40)


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


class VoiceTurn(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: str
    transcript: str
    response: str
    intent: VoiceIntent
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VoiceReply(BaseModel):
    ok: bool
    assistant_name: str
    text: str
    intent: VoiceIntent
    requires_confirmation: bool = False
    confirmation_id: UUID | None = None
    speak_text: str | None = None
    ui_action: str | None = None
    ui_target: str | None = None
    session_active: bool = False
    sensitive_data_redacted: bool = True


class VoiceHistory(BaseModel):
    items: list[VoiceTurn]
    count: int


class VoiceStatus(BaseModel):
    settings: VoiceSettings
    pending_confirmations: int
    active_sessions: int = 0
    browser_speech_supported: bool = True
    push_to_talk_supported: bool = True
    telegram_voice_supported: bool = True
    raw_audio_stored: bool = False
    automatic_execution: bool = False
    automatic_order_execution: bool = False
    automatic_merge: bool = False
