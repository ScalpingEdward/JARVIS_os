from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class OptionsFlowState(str, Enum):
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
    GAMMA_SHIFT = "gamma-shift"
    VOLATILITY_SHIFT = "volatility-shift"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class OptionObservation:
    source_key: str
    underlying: str
    expiry: str
    strike: float
    option_type: str
    side: str
    premium: float
    contracts: int
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    implied_volatility: float = 0.0
    open_interest: int = 0
    volume: int = 0
    confidence: float = 0.5
    freshness: float = 1.0
    provenance: str = "unknown"


@dataclass
class OptionsFlowRecord:
    record_id: str
    workspace_id: str
    observations: list[OptionObservation]
    state: OptionsFlowState = OptionsFlowState.DRAFT
    net_premium: float = 0.0
    call_put_pressure: float = 0.0
    dealer_gamma_exposure: float = 0.0
    gamma_concentration: float = 0.0
    volatility_pressure: float = 0.0
    quality_score: float = 0.0
    confidence_score: float = 0.0
    risk_score: float = 0.0
    human_approved: bool = False
    risk_brain_blocked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
