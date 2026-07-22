from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class MarketBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class StructureState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    ANALYSIS_PENDING = "analysis-pending"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    STRUCTURE_READY = "structure-ready"
    APPROVED = "approved"
    ISSUED_TO_VISUALIZER = "issued-to-visualizer"
    INVALIDATED = "invalidated"
    ARCHIVED = "archived"


class SwingPoint(BaseModel):
    timestamp: datetime
    price: float
    kind: Literal["high", "low"]
    strength: int = Field(default=1, ge=1, le=10)


class ImbalanceZone(BaseModel):
    zone_id: str = Field(default_factory=lambda: str(uuid4()))
    kind: Literal["fvg", "order-block", "breaker", "liquidity", "support", "resistance"]
    low: float
    high: float
    timeframe: str = Field(min_length=1, max_length=20)
    mitigated: bool = False

    @model_validator(mode="after")
    def validate_zone(self) -> "ImbalanceZone":
        if self.low > self.high:
            raise ValueError("zone low cannot exceed zone high")
        return self


class MarketStructureCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    symbol: str = Field(min_length=1, max_length=40)
    timeframe: str = Field(min_length=1, max_length=20)
    higher_timeframe: str = Field(min_length=1, max_length=20)
    current_price: float
    swings: list[SwingPoint] = Field(min_length=4, max_length=500)
    zones: list[ImbalanceZone] = Field(default_factory=list)
    liquidity_sweep: bool = False
    displacement_confirmed: bool = False
    bos_confirmed: bool = False
    choch_confirmed: bool = False
    session_alignment: bool = False
    news_risk_active: bool = False
    risk_brain_hard_block: bool = False
    evidence_refs: list[str] = Field(default_factory=list)
    minimum_confluence_score: float = Field(default=65, ge=0, le=100)

    @model_validator(mode="after")
    def validate_swings(self) -> "MarketStructureCreate":
        ordered = sorted(self.swings, key=lambda item: item.timestamp)
        if ordered != self.swings:
            raise ValueError("swings must be ordered chronologically")
        if len({item.timestamp for item in self.swings}) != len(self.swings):
            raise ValueError("swing timestamps must be unique")
        return self


class StructureSignal(BaseModel):
    key: str
    present: bool
    weight: float
    contribution: float
    detail: str


class MarketStructureRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    symbol: str
    timeframe: str
    higher_timeframe: str
    state: StructureState
    bias: MarketBias = MarketBias.NEUTRAL
    confluence_score: float = 0
    premium_discount_position: float = 50
    nearest_liquidity_above: float | None = None
    nearest_liquidity_below: float | None = None
    active_zones: list[ImbalanceZone] = Field(default_factory=list)
    signals: list[StructureSignal] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    approval_token: str | None = None
    downstream_receipt: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StructureCommand(str, Enum):
    APPROVE = "approve"
    ISSUE = "issue"
    INVALIDATE = "invalidate"
    ARCHIVE = "archive"


class StructureAction(BaseModel):
    command: StructureCommand
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = None
    downstream_receipt: str | None = None
    reason: str | None = Field(default=None, max_length=4000)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    record_id: str
    action: str
    actor: str
    from_state: str | None = None
    to_state: str
    detail: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
