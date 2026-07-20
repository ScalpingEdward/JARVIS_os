from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TelegramTransportState(str, Enum):
    blocked = "blocked"
    session_required = "session-required"
    flood_wait = "flood-wait"
    reconnect_required = "reconnect-required"
    transport_ready = "transport-ready"
    dispatched = "dispatched"


class TransportAttempt(BaseModel):
    attempt_number: int = Field(ge=1, le=10)
    connected: bool = False
    authenticated: bool = False
    read_only_verified: bool = True
    media_retrieved: bool = False
    timed_out: bool = False
    retryable: bool = False
    latency_ms: int = Field(default=0, ge=0)
    flood_wait_seconds: int = Field(default=0, ge=0)
    reconnect_count: int = Field(default=0, ge=0)
    error_code: str | None = Field(default=None, max_length=120)


class TelegramTransportPolicy(BaseModel):
    maximum_attempts: int = Field(default=3, ge=1, le=10)
    maximum_latency_ms: int = Field(default=20_000, gt=0)
    maximum_flood_wait_seconds: int = Field(default=300, ge=0)
    maximum_reconnects: int = Field(default=3, ge=0)
    require_isolated_session_reference: bool = True
    require_read_only_transport: bool = True
    allow_bot_api_transport: bool = True
    allow_telethon_transport: bool = True


class TelegramTransportAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    collector_assessment_id: str = Field(min_length=1, max_length=120)
    collector_state: str = Field(min_length=1, max_length=40)
    transport_id: str = Field(min_length=1, max_length=100)
    transport_type: str = Field(pattern="^(telethon|bot-api)$")
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    telegram_message_id: str = Field(min_length=1, max_length=120)
    session_reference: str | None = Field(default=None, max_length=250)
    session_resolved: bool = False
    session_embedded: bool = False
    risk_brain_clear: bool = True
    attempts: list[TransportAttempt] = Field(min_length=1, max_length=10)
    policy: TelegramTransportPolicy = Field(default_factory=TelegramTransportPolicy)


class TelegramTransportScores(BaseModel):
    session_isolation: int = Field(ge=0, le=100)
    connection_reliability: int = Field(ge=0, le=100)
    authentication_quality: int = Field(ge=0, le=100)
    latency_quality: int = Field(ge=0, le=100)
    rate_limit_safety: int = Field(ge=0, le=100)
    transport_confidence: int = Field(ge=0, le=100)


class TelegramTransportAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    collector_assessment_id: str
    transport_id: str
    transport_type: str
    telegram_chat_id: str
    telegram_message_id: str
    state: TelegramTransportState
    selected_attempt_number: int | None
    dispatchable: bool
    target_module: str | None
    recommended_action: str
    scores: TelegramTransportScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelegramTransportStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: TelegramTransportState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
