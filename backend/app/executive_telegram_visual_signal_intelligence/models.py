from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class VisualSignalState(str, Enum):
    rejected = "rejected"
    manual_review = "manual-review"
    parsed = "parsed"
    validated = "validated"
    actionable = "actionable"


class TradeDirection(str, Enum):
    long = "long"
    short = "short"
    neutral = "neutral"
    unknown = "unknown"


class ChartAnnotation(BaseModel):
    symbol: str | None = Field(default=None, max_length=40)
    timeframe: str | None = Field(default=None, max_length=20)
    direction: TradeDirection = TradeDirection.unknown
    entry_low: float | None = None
    entry_high: float | None = None
    stop_loss: float | None = None
    take_profits: list[float] = Field(default_factory=list, max_length=10)
    ict_concepts: list[str] = Field(default_factory=list, max_length=30)
    liquidity_levels: list[float] = Field(default_factory=list, max_length=20)
    order_blocks: list[str] = Field(default_factory=list, max_length=20)
    fair_value_gaps: list[str] = Field(default_factory=list, max_length=20)
    market_structure_notes: list[str] = Field(default_factory=list, max_length=30)
    extracted_text: list[str] = Field(default_factory=list, max_length=50)


class VisualSignalPolicy(BaseModel):
    minimum_image_quality_score: int = Field(default=65, ge=0, le=100)
    minimum_ocr_confidence: int = Field(default=70, ge=0, le=100)
    minimum_direction_confidence: int = Field(default=75, ge=0, le=100)
    minimum_structure_confidence: int = Field(default=70, ge=0, le=100)
    minimum_signal_confidence: int = Field(default=80, ge=0, le=100)
    require_symbol: bool = True
    require_timeframe: bool = True
    require_risk_levels: bool = True
    require_human_approval: bool = True


class VisualSignalAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    telegram_message_id: str = Field(min_length=1, max_length=120)
    image_reference: str = Field(min_length=1, max_length=500)
    image_sha256: str = Field(min_length=16, max_length=128)
    image_quality_score: int = Field(ge=0, le=100)
    ocr_confidence: int = Field(ge=0, le=100)
    direction_confidence: int = Field(ge=0, le=100)
    structure_confidence: int = Field(ge=0, le=100)
    risk_brain_clear: bool = True
    human_approved: bool = False
    annotation: ChartAnnotation
    policy: VisualSignalPolicy = Field(default_factory=VisualSignalPolicy)


class VisualSignalScores(BaseModel):
    image_quality: int = Field(ge=0, le=100)
    text_extraction: int = Field(ge=0, le=100)
    direction_detection: int = Field(ge=0, le=100)
    ict_structure: int = Field(ge=0, le=100)
    risk_completeness: int = Field(ge=0, le=100)
    signal_confidence: int = Field(ge=0, le=100)


class VisualSignalAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    telegram_chat_id: str
    telegram_message_id: str
    image_reference: str
    image_sha256: str
    state: VisualSignalState
    usable_for_strategy_review: bool
    executable: bool = False
    recommended_action: str
    normalized_signal: ChartAnnotation
    scores: VisualSignalScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VisualSignalStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: VisualSignalState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
