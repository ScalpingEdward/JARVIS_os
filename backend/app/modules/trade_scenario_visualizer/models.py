from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ScenarioDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class ScenarioState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    DRAFT = "draft"
    READY = "ready"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    PUBLISHED = "published"
    INVALIDATED = "invalidated"
    ARCHIVED = "archived"


class PriceZone(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    low: float
    high: float
    kind: Literal["entry", "stop", "target", "liquidity", "fvg", "order-block", "support", "resistance"]

    @model_validator(mode="after")
    def validate_range(self) -> "PriceZone":
        if self.low > self.high:
            raise ValueError("zone low cannot exceed zone high")
        return self


class ScenarioPoint(BaseModel):
    timestamp: datetime
    price: float
    label: str = Field(min_length=1, max_length=160)
    kind: Literal["entry", "stop", "target", "invalidation", "liquidity", "bos", "choch", "note"]


class TradeScenarioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    symbol: str = Field(min_length=1, max_length=40)
    timeframe: str = Field(min_length=1, max_length=20)
    direction: ScenarioDirection
    thesis: str = Field(min_length=1, max_length=6000)
    entry_price: float
    stop_price: float
    target_prices: list[float] = Field(min_length=1, max_length=10)
    confidence_score: float = Field(ge=0, le=100)
    risk_reward_minimum: float = Field(default=1.0, gt=0, le=100)
    setup_evidence: dict[str, Any] = Field(default_factory=dict)
    risk_brain_hard_block: bool = False
    zones: list[PriceZone] = Field(default_factory=list)
    points: list[ScenarioPoint] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_trade_geometry(self) -> "TradeScenarioCreate":
        if self.direction == ScenarioDirection.LONG:
            if self.stop_price >= self.entry_price:
                raise ValueError("long stop must be below entry")
            if any(target <= self.entry_price for target in self.target_prices):
                raise ValueError("long targets must be above entry")
        elif self.direction == ScenarioDirection.SHORT:
            if self.stop_price <= self.entry_price:
                raise ValueError("short stop must be above entry")
            if any(target >= self.entry_price for target in self.target_prices):
                raise ValueError("short targets must be below entry")
        return self


class ChartAnnotation(BaseModel):
    annotation_type: Literal["line", "box", "label", "arrow"]
    label: str
    price: float | None = None
    price_low: float | None = None
    price_high: float | None = None
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TradeScenarioRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    symbol: str
    timeframe: str
    direction: ScenarioDirection
    state: ScenarioState
    thesis: str
    entry_price: float
    stop_price: float
    target_prices: list[float]
    risk_reward_ratios: list[float] = Field(default_factory=list)
    confidence_score: float
    annotations: list[ChartAnnotation] = Field(default_factory=list)
    tradingview_payload: dict[str, Any] = Field(default_factory=dict)
    review_token: str | None = None
    publish_receipt: str | None = None
    notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ScenarioCommand(str, Enum):
    APPROVE = "approve"
    PUBLISH = "publish"
    INVALIDATE = "invalidate"
    ARCHIVE = "archive"


class ScenarioAction(BaseModel):
    command: ScenarioCommand
    actor: str = Field(min_length=1, max_length=180)
    review_token: str | None = None
    publish_receipt: str | None = None
    reason: str | None = Field(default=None, max_length=4000)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    record_id: str
    action: str
    actor: str
    from_state: str | None = None
    to_state: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
