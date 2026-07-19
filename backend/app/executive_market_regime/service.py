from threading import RLock
from uuid import UUID

from .models import (
    AuditRecord,
    MarketRegime,
    MarketRegimeAssessment,
    RegimeAssessmentCreate,
    RegimeDecision,
    RegimeStatusResponse,
    RegimeStrategyEvaluationRequest,
    RegimeStrategyEvaluationResponse,
    StrategyRegimeEvaluation,
)


class ExecutiveMarketRegimeService:
    def __init__(self) -> None:
        self._assessments: dict[UUID, MarketRegimeAssessment] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    def status(self, workspace_id: str) -> RegimeStatusResponse:
        items = self.list_assessments(workspace_id)
        latest = max(items, key=lambda item: item.observed_at) if items else None
        return RegimeStatusResponse(
            workspace_id=workspace_id,
            assessments=len(items),
            latest_regime=latest.primary_regime if latest else None,
        )

    def assess(self, payload: RegimeAssessmentCreate) -> MarketRegimeAssessment:
        primary, secondary, confidence, reasons = self._classify(payload)
        tradability = RegimeDecision.allow
        if payload.features.liquidity_score < payload.policy.minimum_liquidity:
            tradability = RegimeDecision.block
            reasons.append("Liquidity is below the governed minimum")
        elif payload.features.news_risk > payload.policy.maximum_news_risk:
            tradability = RegimeDecision.block
            reasons.append("News risk exceeds the governed maximum")
        elif confidence < payload.policy.minimum_confidence:
            tradability = RegimeDecision.shadow_only if payload.policy.shadow_below_confidence else RegimeDecision.block
            reasons.append("Regime confidence is below the governed minimum")

        assessment = MarketRegimeAssessment(
            workspace_id=payload.workspace_id,
            account_profile_id=payload.account_profile_id,
            symbol=payload.symbol.upper(),
            timeframe=payload.timeframe.upper(),
            observed_at=payload.observed_at,
            primary_regime=primary,
            secondary_regimes=secondary,
            confidence=round(confidence, 4),
            tradability=tradability,
            reasons=reasons,
            features=payload.features,
            policy=payload.policy,
            created_by=payload.actor_id,
        )
        with self._lock:
            self._assessments[assessment.id] = assessment
            self._audit.append(AuditRecord(
                workspace_id=payload.workspace_id,
                actor_id=payload.actor_id,
                action="market_regime_assessed",
                entity_id=assessment.id,
                details={"regime": primary.value, "tradability": tradability.value},
            ))
        return assessment

    def get(self, assessment_id: UUID, workspace_id: str) -> MarketRegimeAssessment | None:
        item = self._assessments.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_assessments(self, workspace_id: str, account_profile_id: str | None = None) -> list[MarketRegimeAssessment]:
        items = [item for item in self._assessments.values() if item.workspace_id == workspace_id]
        if account_profile_id is not None:
            items = [item for item in items if item.account_profile_id == account_profile_id]
        return sorted(items, key=lambda item: item.observed_at, reverse=True)

    def evaluate_strategies(
        self,
        assessment_id: UUID,
        payload: RegimeStrategyEvaluationRequest,
    ) -> RegimeStrategyEvaluationResponse:
        assessment = self.get(assessment_id, payload.workspace_id)
        if assessment is None:
            raise KeyError("Market-regime assessment not found")

        evaluations: list[StrategyRegimeEvaluation] = []
        for rule in payload.rules:
            if assessment.tradability == RegimeDecision.block:
                decision = RegimeDecision.block
                reason = "Assessment-level safety gate blocks strategy activation"
            elif assessment.primary_regime in rule.blocked_regimes:
                decision = RegimeDecision.block
                reason = "Primary regime is explicitly blocked for this strategy"
            elif assessment.primary_regime in rule.allowed_regimes and assessment.tradability == RegimeDecision.allow:
                decision = RegimeDecision.allow
                reason = "Strategy is approved for the detected primary regime"
            elif assessment.primary_regime in rule.shadow_regimes or assessment.tradability == RegimeDecision.shadow_only:
                decision = RegimeDecision.shadow_only
                reason = "Strategy may collect evidence in shadow mode only"
            else:
                decision = RegimeDecision.block
                reason = "No governed permission exists for this strategy-regime pair"
            evaluations.append(StrategyRegimeEvaluation(strategy_id=rule.strategy_id, decision=decision, reason=reason))

        with self._lock:
            self._audit.append(AuditRecord(
                workspace_id=payload.workspace_id,
                actor_id=payload.actor_id,
                action="strategy_regime_evaluated",
                entity_id=assessment.id,
                details={"strategies": len(evaluations), "regime": assessment.primary_regime.value},
            ))
        return RegimeStrategyEvaluationResponse(
            assessment_id=assessment.id,
            primary_regime=assessment.primary_regime,
            evaluations=evaluations,
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    @staticmethod
    def _classify(payload: RegimeAssessmentCreate) -> tuple[MarketRegime, list[MarketRegime], float, list[str]]:
        f = payload.features
        candidates: list[tuple[MarketRegime, float, str]] = []
        candidates.append((MarketRegime.strong_trend, 0.55 * f.trend_strength + 0.25 * abs(f.directional_imbalance) + 0.20 * f.volume_confirmation, "Directional trend strength and confirmation dominate"))
        candidates.append((MarketRegime.range, 0.55 * f.range_efficiency + 0.25 * (1 - f.trend_strength) + 0.20 * (1 - f.expansion_score), "Range efficiency dominates directional movement"))
        candidates.append((MarketRegime.compression, 0.60 * f.compression_score + 0.25 * (1 - f.volatility_percentile) + 0.15 * (1 - f.expansion_score), "Volatility and price movement are compressed"))
        candidates.append((MarketRegime.expansion, 0.50 * f.expansion_score + 0.30 * f.volatility_percentile + 0.20 * f.volume_confirmation, "Volatility and directional range are expanding"))
        candidates.append((MarketRegime.high_volatility, 0.70 * f.volatility_percentile + 0.30 * f.expansion_score, "Volatility percentile is elevated"))
        candidates.append((MarketRegime.low_volatility, 0.70 * (1 - f.volatility_percentile) + 0.30 * f.compression_score, "Volatility percentile is subdued"))
        candidates.append((MarketRegime.news_driven, 0.80 * f.news_risk + 0.20 * f.expansion_score, "News risk dominates current conditions"))
        candidates.append((MarketRegime.illiquid, 0.80 * (1 - f.liquidity_score) + 0.20 * (1 - f.volume_confirmation), "Liquidity and volume confirmation are weak"))

        candidates.sort(key=lambda row: row[1], reverse=True)
        primary, confidence, reason = candidates[0]
        if primary == MarketRegime.strong_trend and confidence < 0.72:
            primary = MarketRegime.weak_trend
        secondary = [regime for regime, score, _ in candidates[1:4] if score >= 0.58 and regime != primary]
        if confidence < 0.45:
            primary = MarketRegime.unknown
        return primary, secondary, min(confidence, 1.0), [reason]


executive_market_regime_service = ExecutiveMarketRegimeService()
