from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class MicrostructureState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    SCORED = "scored"
    POLICY_READY = "policy-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    STABLE = "stable"
    LIQUIDITY_SHIFT = "liquidity-shift"
    ORDER_FLOW_IMBALANCE = "order-flow-imbalance"
    FRAGMENTATION_ALERT = "fragmentation-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class VenueObservation(BaseModel):
    venue: str = Field(min_length=1, max_length=80)
    instrument: str = Field(min_length=1, max_length=40)
    bid: float = Field(gt=0)
    ask: float = Field(gt=0)
    bid_size: float = Field(ge=0)
    ask_size: float = Field(ge=0)
    traded_volume: float = Field(ge=0)
    cancel_rate: float = Field(ge=0, le=1)
    latency_ms: float = Field(ge=0)
    observed_at: datetime

    @model_validator(mode="after")
    def validate_book(self) -> "VenueObservation":
        if self.ask < self.bid:
            raise ValueError("ask must be greater than or equal to bid")
        return self


class MicrostructureRecordCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=80)
    source_key: str = Field(min_length=1, max_length=160)
    asset_class: Literal[
        "equities", "rates", "credit", "fx", "commodities", "crypto", "options"
    ]
    observations: list[VenueObservation] = Field(min_length=1, max_length=200)
    provenance_confidence: float = Field(ge=0, le=1)
    freshness_score: float = Field(ge=0, le=1)
    human_approval_required: bool = True


class MicrostructureScores(BaseModel):
    spread_stress: float = Field(ge=0, le=100)
    depth_resilience: float = Field(ge=0, le=100)
    order_flow_imbalance: float = Field(ge=-100, le=100)
    fragmentation_risk: float = Field(ge=0, le=100)
    execution_quality: float = Field(ge=0, le=100)
    liquidity_confidence: float = Field(ge=0, le=100)


class MicrostructureRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    asset_class: str
    state: MicrostructureState = MicrostructureState.DRAFT
    scores: MicrostructureScores | None = None
    approved_by: str | None = None
    created_at: datetime
    updated_at: datetime


class MicrostructureAction(BaseModel):
    action: Literal[
        "score", "submit-review", "approve", "activate", "monitor", "suspend", "revoke", "archive"
    ]
    actor: str = Field(min_length=1, max_length=120)
    operation_receipt: str = Field(min_length=8, max_length=200)
    reason: str | None = Field(default=None, max_length=500)
    risk_brain_blocked: bool = False
