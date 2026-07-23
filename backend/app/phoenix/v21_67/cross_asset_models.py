"""PHOENIX v21.67 cross-asset intelligence governance models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping, Sequence


class CrossAssetState(str, Enum):
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
    CORRELATION_SHIFT = "correlation-shift"
    REGIME_DIVERGENCE = "regime-divergence"
    CONTAGION_ALERT = "contagion-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AssetClass(str, Enum):
    EQUITY = "equity"
    RATES = "rates"
    CREDIT = "credit"
    FX = "fx"
    COMMODITY = "commodity"
    CRYPTO = "crypto"
    VOLATILITY = "volatility"
    LIQUIDITY = "liquidity"


@dataclass(frozen=True)
class AssetObservation:
    symbol: str
    asset_class: AssetClass
    return_score: float
    volatility_score: float
    liquidity_score: float
    stress_score: float
    freshness: float
    confidence: float
    provenance: str


@dataclass(frozen=True)
class CrossAssetRecord:
    record_id: str
    workspace_id: str
    source_key: str
    observations: Sequence[AssetObservation]
    correlations: Mapping[str, float] = field(default_factory=dict)
    state: CrossAssetState = CrossAssetState.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    approved_by: str | None = None
    risk_blocked: bool = False


@dataclass(frozen=True)
class CrossAssetScore:
    directional_alignment: float
    diversification_health: float
    correlation_stability: float
    contagion_risk: float
    liquidity_stress: float
    confidence: float
    dispersion: float
    recommended_state: CrossAssetState
