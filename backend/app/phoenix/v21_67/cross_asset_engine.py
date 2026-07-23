"""Scoring and regime detection for PHOENIX v21.67."""

from __future__ import annotations

from math import sqrt
from statistics import fmean, pstdev

from .cross_asset_models import CrossAssetRecord, CrossAssetScore, CrossAssetState


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


class CrossAssetEngine:
    """Produces governed cross-asset intelligence without execution authority."""

    def score(self, record: CrossAssetRecord) -> CrossAssetScore:
        if record.risk_blocked or not record.observations:
            return CrossAssetScore(0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0, CrossAssetState.BLOCKED)

        returns = [item.return_score for item in record.observations]
        vol = [item.volatility_score for item in record.observations]
        liquidity = [item.liquidity_score for item in record.observations]
        stress = [item.stress_score for item in record.observations]
        quality = [sqrt(_clamp(item.freshness) * _clamp(item.confidence)) for item in record.observations]
        correlation_values = list(record.correlations.values())

        alignment = _clamp(abs(fmean(returns)))
        dispersion = _clamp(pstdev(returns) if len(returns) > 1 else 0.0)
        diversification = _clamp(1.0 - fmean(abs(value) for value in correlation_values)) if correlation_values else 0.5
        correlation_stability = _clamp(1.0 - (pstdev(correlation_values) if len(correlation_values) > 1 else 0.0))
        liquidity_stress = _clamp(fmean((1.0 - _clamp(liq)) for liq in liquidity))
        contagion = _clamp(0.40 * fmean(stress) + 0.25 * fmean(vol) + 0.20 * liquidity_stress + 0.15 * alignment)
        confidence = _clamp(fmean(quality))

        state = CrossAssetState.SCORED
        if confidence < 0.55:
            state = CrossAssetState.REVIEW_REQUIRED
        elif contagion >= 0.82:
            state = CrossAssetState.ESCALATED
        elif contagion >= 0.70:
            state = CrossAssetState.CONTAGION_ALERT
        elif correlation_stability < 0.45:
            state = CrossAssetState.CORRELATION_SHIFT
        elif dispersion >= 0.62:
            state = CrossAssetState.REGIME_DIVERGENCE
        elif record.approved_by:
            state = CrossAssetState.ACTIVE

        return CrossAssetScore(
            directional_alignment=alignment,
            diversification_health=diversification,
            correlation_stability=correlation_stability,
            contagion_risk=contagion,
            liquidity_stress=liquidity_stress,
            confidence=confidence,
            dispersion=dispersion,
            recommended_state=state,
        )
