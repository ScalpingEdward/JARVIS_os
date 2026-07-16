from __future__ import annotations

from uuid import UUID

from .models import (
    ExecutionStep,
    ForecastRequest,
    MarketRegime,
    OpportunityScore,
    PredictiveReport,
    PredictiveStatus,
    ScenarioForecast,
    ScenarioType,
    WhatIfImpact,
    WhatIfReport,
    WhatIfRequest,
)


class PredictiveIntelligenceService:
    def __init__(self) -> None:
        self._reports: dict[UUID, PredictiveReport] = {}

    def reset(self) -> None:
        self._reports.clear()

    def status(self) -> PredictiveStatus:
        return PredictiveStatus(reports=len(self._reports))

    def generate(self, payload: ForecastRequest) -> PredictiveReport:
        scenarios: list[ScenarioForecast] = []
        raw_opportunities: list[tuple[str, float, float, float]] = []
        for signal in payload.signals:
            edge = max(0.0, min(1.0, (signal.structure_score + signal.orderflow_score + signal.liquidity_score) / 3))
            risk = max(0.0, min(1.0, (signal.volatility_score + signal.news_risk) / 2))
            score = round((edge * 0.55 + signal.confidence * 0.30 + (1 - risk) * 0.15) * 100, 2)
            raw_opportunities.append((signal.symbol, score, edge, risk))
            primary = self._primary_scenario(signal.regime, signal.news_risk, signal.liquidity_score)
            probability = round(max(0.05, min(0.95, edge * 0.55 + signal.confidence * 0.35 + 0.10)), 3)
            scenarios.append(
                ScenarioForecast(
                    symbol=signal.symbol,
                    scenario=primary,
                    probability=probability,
                    confidence=signal.confidence,
                    expected_volatility=signal.volatility_score,
                    risk_score=risk,
                    rationale=[
                        f"Structure score {signal.structure_score:.2f}",
                        f"Orderflow score {signal.orderflow_score:.2f}",
                        f"News risk {signal.news_risk:.2f}",
                    ],
                )
            )

        ranked = sorted(raw_opportunities, key=lambda item: item[1], reverse=True)
        opportunities = [
            OpportunityScore(symbol=symbol, score=score, edge=edge, risk_score=risk, confidence=self._confidence_for(payload, symbol), rank=index)
            for index, (symbol, score, edge, risk) in enumerate(ranked, start=1)
        ]
        top = opportunities[0]
        plan = [
            ExecutionStep(order=1, instruction=f"Monitor {top.symbol} for liquidity interaction."),
            ExecutionStep(order=2, instruction="Wait for structural confirmation such as BOS or CHOCH."),
            ExecutionStep(order=3, instruction="Validate spread, news risk, invalidation and account drawdown."),
            ExecutionStep(order=4, instruction="Present the setup to MASTER Brano for explicit approval."),
        ]
        recommendation = (
            f"MASTER Brano, {top.symbol} ranks first with score {top.score:.1f}. "
            "Remain in advisory mode and wait for confirmation before any action."
        )
        report = PredictiveReport(
            horizon_minutes=payload.horizon_minutes,
            scenarios=scenarios,
            opportunities=opportunities,
            execution_plan=plan,
            executive_recommendation=recommendation,
        )
        self._reports[report.id] = report
        return report

    def list_reports(self) -> list[PredictiveReport]:
        return list(self._reports.values())

    def get(self, report_id: UUID) -> PredictiveReport | None:
        return self._reports.get(report_id)

    def what_if(self, payload: WhatIfRequest) -> WhatIfReport:
        impacts = []
        event_lower = payload.event.lower()
        for symbol in payload.affected_symbols:
            if "higher" in event_lower or "hawkish" in event_lower or "dxy" in event_lower:
                bias = "bearish" if symbol.upper() in {"XAUUSD", "BTCUSD", "NAS100"} else "mixed"
            elif "lower" in event_lower or "dovish" in event_lower:
                bias = "bullish" if symbol.upper() in {"XAUUSD", "BTCUSD", "NAS100"} else "mixed"
            else:
                bias = "uncertain"
            impacts.append(
                WhatIfImpact(
                    symbol=symbol,
                    directional_bias=bias,
                    volatility_impact=payload.shock_strength,
                    risk_impact=min(1.0, payload.shock_strength * 0.9),
                    confidence=0.65,
                )
            )
        return WhatIfReport(
            event=payload.event,
            impacts=impacts,
            recommendation="Reduce certainty, verify live data and require human approval before acting.",
        )

    @staticmethod
    def _primary_scenario(regime: MarketRegime, news_risk: float, liquidity_score: float) -> ScenarioType:
        if news_risk >= 0.75:
            return ScenarioType.news_shock
        if liquidity_score >= 0.8:
            return ScenarioType.liquidity_sweep_reversal
        if regime == MarketRegime.trending:
            return ScenarioType.bullish_continuation
        if regime == MarketRegime.volatile:
            return ScenarioType.range_expansion
        return ScenarioType.trend_failure

    @staticmethod
    def _confidence_for(payload: ForecastRequest, symbol: str) -> float:
        return next(signal.confidence for signal in payload.signals if signal.symbol == symbol)


predictive_intelligence_service = PredictiveIntelligenceService()
