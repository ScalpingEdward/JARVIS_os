from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class VisionSignalState(str, Enum):
    rejected = "rejected"
    needs_review = "needs-review"
    context_required = "context-required"
    validated = "validated"
    risk_eligible = "risk-eligible"


class ICTFeatures(BaseModel):
    fair_value_gap: bool = False
    order_block: bool = False
    liquidity_sweep: bool = False
    break_of_structure: bool = False
    change_of_character: bool = False
    premium_discount: bool = False
    killzone_context: bool = False


class ChartSignalExtraction(BaseModel):
    symbol: str | None = Field(default=None, max_length=30)
    timeframe: str | None = Field(default=None, max_length=20)
    direction: str | None = Field(default=None, pattern="^(long|short)$")
    entry_price: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    ocr_confidence: int = Field(ge=0, le=100)
    visual_confidence: int = Field(ge=0, le=100)
    chart_quality_score: int = Field(ge=0, le=100)
    ict: ICTFeatures = Field(default_factory=ICTFeatures)


class VisionSignalPolicy(BaseModel):
    minimum_ocr_confidence: int = Field(default=70, ge=0, le=100)
    minimum_visual_confidence: int = Field(default=75, ge=0, le=100)
    minimum_chart_quality_score: int = Field(default=65, ge=0, le=100)
    minimum_ict_confluences: int = Field(default=2, ge=0, le=7)
    minimum_risk_reward: float = Field(default=1.5, gt=0)
    require_symbol: bool = True
    require_timeframe: bool = True
    require_levels: bool = True


class VisionSignalAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    telegram_message_id: str = Field(min_length=1, max_length=120)
    image_sha256: str = Field(min_length=32, max_length=64)
    extraction: ChartSignalExtraction
    market_context_confirmed: bool = False
    risk_brain_clear: bool = True
    human_approved: bool = False
    policy: VisionSignalPolicy = Field(default_factory=VisionSignalPolicy)


class VisionSignalScores(BaseModel):
    extraction_confidence: int = Field(ge=0, le=100)
    ict_confluence: int = Field(ge=0, le=100)
    level_integrity: int = Field(ge=0, le=100)
    risk_reward_quality: int = Field(ge=0, le=100)
    signal_confidence: int = Field(ge=0, le=100)


class VisionSignalAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    telegram_chat_id: str
    telegram_message_id: str
    image_sha256: str
    state: VisionSignalState
    symbol: str | None
    timeframe: str | None
    direction: str | None
    risk_reward: float | None
    trade_candidate: bool
    recommended_action: str
    detected_features: list[str]
    scores: VisionSignalScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VisionSignalStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: VisionSignalState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
