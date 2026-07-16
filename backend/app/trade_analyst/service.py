from uuid import UUID

from .models import (
    AnalystVerdict,
    RiskLevel,
    TradeAnalysisCreate,
    TradeAnalysisRecord,
    TradeAnalystStatus,
    TradeDirection,
)


class TradeAnalystService:
    def __init__(self) -> None:
        self._analyses: dict[UUID, TradeAnalysisRecord] = {}

    def reset(self) -> None:
        self._analyses.clear()

    def create(self, payload: TradeAnalysisCreate) -> TradeAnalysisRecord:
        direction_sign = 1 if payload.direction == TradeDirection.long else -1 if payload.direction == TradeDirection.short else 0
        directional_inputs = [
            payload.structure_score * direction_sign,
            payload.liquidity_score * direction_sign,
            payload.orderflow_score * direction_sign,
            payload.memory_edge * direction_sign,
        ]
        factor_score = sum(item.score * item.confidence for item in payload.factors) / max(len(payload.factors), 1)
        simulation = ((payload.simulation_probability - 0.5) * 2) if payload.simulation_probability is not None else 0
        alignment = sum(directional_inputs) / len(directional_inputs)
        score = (
            alignment * 0.42
            + factor_score * 0.18
            + simulation * 0.15
            + (payload.data_quality - 0.5) * 0.3
            - payload.macro_risk * 0.18
            - payload.correlation_risk * 0.12
        )
        score = round(max(-1, min(1, score)), 4)
        confidence = round(max(0, min(1, payload.data_quality * 0.45 + abs(score) * 0.4 + (0.15 if payload.factors else 0))), 4)

        total_risk = max(payload.macro_risk, payload.correlation_risk, 1 - payload.data_quality)
        if total_risk >= 0.85:
            risk_level = RiskLevel.extreme
        elif total_risk >= 0.65:
            risk_level = RiskLevel.high
        elif total_risk >= 0.35:
            risk_level = RiskLevel.moderate
        else:
            risk_level = RiskLevel.low

        if payload.data_quality < 0.35:
            verdict = AnalystVerdict.insufficient_data
        elif risk_level == RiskLevel.extreme or score <= -0.2:
            verdict = AnalystVerdict.avoid
        elif score >= 0.35 and confidence >= 0.55:
            verdict = AnalystVerdict.favorable
        else:
            verdict = AnalystVerdict.conditional

        supporting = []
        opposing = []
        for name, value in (
            ("market structure", directional_inputs[0]),
            ("liquidity context", directional_inputs[1]),
            ("orderflow", directional_inputs[2]),
            ("historical memory", directional_inputs[3]),
            ("simulation", simulation),
        ):
            if value > 0.15:
                supporting.append(name)
            elif value < -0.15:
                opposing.append(name)
        for factor in payload.factors:
            (supporting if factor.score > 0 else opposing).append(factor.name)

        risks = []
        if payload.macro_risk >= 0.5:
            risks.append("Elevated macro-event risk")
        if payload.correlation_risk >= 0.5:
            risks.append("Elevated correlated-exposure risk")
        if payload.data_quality < 0.6:
            risks.append("Incomplete or low-quality market data")
        if payload.higher_timeframe_bias not in {TradeDirection.neutral, payload.direction}:
            risks.append("Trade conflicts with higher-timeframe bias")

        rr = self._risk_reward(payload)
        primary = f"{payload.direction.value.upper()} thesis remains valid while price respects the invalidation level."
        alternative = "Stand aside or reassess if structure, orderflow, or macro conditions invalidate the thesis."
        invalidation_reason = (
            f"Thesis invalid below/above {payload.invalidation_price}."
            if payload.invalidation_price is not None
            else "No explicit invalidation price supplied; execution should remain blocked."
        )

        record = TradeAnalysisRecord(
            symbol=payload.symbol.upper(),
            direction=payload.direction,
            verdict=verdict,
            confidence=confidence,
            risk_level=risk_level,
            composite_score=score,
            current_price=payload.current_price,
            entry_zone=payload.entry_zone,
            invalidation_price=payload.invalidation_price,
            target_prices=payload.target_prices,
            risk_reward=rr,
            supporting_factors=supporting,
            opposing_factors=opposing,
            risks=risks,
            primary_scenario=primary,
            alternative_scenario=alternative,
            invalidation_reason=invalidation_reason,
            data_quality=payload.data_quality,
        )
        self._analyses[record.id] = record
        return record

    def _risk_reward(self, payload: TradeAnalysisCreate) -> float | None:
        if payload.invalidation_price is None or not payload.target_prices:
            return None
        entry = payload.current_price
        if payload.entry_zone:
            entry = (payload.entry_zone.low + payload.entry_zone.high) / 2
        risk = abs(entry - payload.invalidation_price)
        reward = abs(payload.target_prices[0] - entry)
        return round(reward / risk, 4) if risk else None

    def get(self, analysis_id: UUID) -> TradeAnalysisRecord | None:
        return self._analyses.get(analysis_id)

    def list_all(self, symbol: str | None = None) -> list[TradeAnalysisRecord]:
        values = list(self._analyses.values())
        if symbol:
            values = [item for item in values if item.symbol == symbol.upper()]
        return sorted(values, key=lambda item: item.created_at, reverse=True)

    def latest(self, symbol: str) -> TradeAnalysisRecord | None:
        values = self.list_all(symbol)
        return values[0] if values else None

    def status(self) -> TradeAnalystStatus:
        values = list(self._analyses.values())
        average = sum(item.confidence for item in values) / len(values) if values else 0
        return TradeAnalystStatus(
            analyses=len(values),
            favorable=sum(item.verdict == AnalystVerdict.favorable for item in values),
            conditional=sum(item.verdict == AnalystVerdict.conditional for item in values),
            avoid=sum(item.verdict == AnalystVerdict.avoid for item in values),
            insufficient_data=sum(item.verdict == AnalystVerdict.insufficient_data for item in values),
            average_confidence=round(average, 4),
        )


trade_analyst_service = TradeAnalystService()
