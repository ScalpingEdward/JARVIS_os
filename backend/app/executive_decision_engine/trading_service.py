from datetime import datetime, timezone
from hashlib import sha256
from threading import RLock
from uuid import UUID

from .trading_models import (
    PortfolioState,
    RiskState,
    TradingDecision,
    TradingDecisionCreate,
    TradingDecisionRecord,
    TradingDecisionStatusResponse,
    TradingDecisionTrace,
)


class TradingDecisionOrchestrationService:
    def __init__(self) -> None:
        self._records: dict[UUID, TradingDecisionRecord] = {}
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def create(self, payload: TradingDecisionCreate) -> TradingDecisionRecord:
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.source_key == payload.source_key for item in self._records.values()):
                raise ValueError("A trading decision already exists for this source key in the workspace")

            ranked = sorted(
                payload.strategies,
                key=lambda item: (item.eligible and not item.blocked, item.adaptive_score, item.confidence),
                reverse=True,
            )
            selected = next((item for item in ranked if item.eligible and not item.blocked), None)
            reasons: list[str] = []
            trace = [
                TradingDecisionTrace(source="market-regime", outcome="evaluated", score=payload.regime_confidence, reason="Market-regime confidence received"),
                TradingDecisionTrace(source="evidence-intelligence", outcome="evaluated", score=payload.evidence_score, reason="Evidence score received"),
                TradingDecisionTrace(source="portfolio-intelligence", outcome=payload.portfolio_state.value, score=payload.portfolio_score, reason="Portfolio state received"),
                TradingDecisionTrace(source="risk-brain", outcome=payload.risk_state.value, score=payload.global_risk_score, reason="Global risk state received"),
            ]

            if payload.risk_state == RiskState.blocked or payload.portfolio_state == PortfolioState.blocked:
                decision = TradingDecision.reject
                selected = None
                reasons.append("Risk Brain or Portfolio Intelligence issued a blocking state")
            elif payload.risk_state == RiskState.frozen or payload.news_risk >= 85:
                decision = TradingDecision.freeze
                selected = None
                reasons.append("Frozen risk state or extreme news risk prevents approval")
            elif selected is None:
                decision = TradingDecision.reject
                reasons.append("No eligible strategy remains after safety filtering")
            elif selected.shadow_only or payload.evidence_score < 55 or payload.regime_confidence < 55:
                decision = TradingDecision.shadow
                reasons.append("Evidence, regime confidence or strategy governance requires shadow operation")
            elif payload.risk_state == RiskState.reduced or payload.portfolio_state == PortfolioState.fragile:
                decision = TradingDecision.reduce
                reasons.append("Risk or portfolio fragility requires reduced exposure")
            elif payload.news_risk >= 65:
                decision = TradingDecision.delay
                reasons.append("Elevated news risk requires delayed execution")
            else:
                decision = TradingDecision.approve
                reasons.append("Regime, evidence, portfolio and risk gates permit approval")

            recommended_weight = 0.0
            if selected is not None and decision in {TradingDecision.approve, TradingDecision.reduce, TradingDecision.delay, TradingDecision.shadow}:
                recommended_weight = selected.portfolio_weight * selected.risk_weight_multiplier
                if decision == TradingDecision.reduce:
                    recommended_weight *= 0.5
                elif decision in {TradingDecision.delay, TradingDecision.shadow}:
                    recommended_weight = 0.0
                reasons.append(f"Selected strategy: {selected.strategy_key}")

            selected_confidence = selected.confidence if selected is not None else 0.0
            confidence = max(0.0, min(100.0, (
                payload.regime_confidence * 0.20
                + payload.evidence_score * 0.25
                + payload.portfolio_score * 0.20
                + selected_confidence * 0.20
                + (100 - payload.global_risk_score) * 0.15
            )))
            quality = max(0.0, min(100.0, (payload.evidence_score + payload.portfolio_score + (selected.adaptive_score if selected else 0.0)) / 3))
            stability = max(0.0, min(100.0, 100 - payload.global_risk_score * 0.6 - payload.news_risk * 0.2))
            consistency = max(0.0, min(100.0, 100 - abs(payload.portfolio_score - payload.evidence_score) * 0.5 - abs(payload.regime_confidence - selected_confidence) * 0.5))
            explainability = min(100.0, 70.0 + len(trace) * 5.0 + len(reasons) * 2.0)
            raw_hash = "|".join([
                payload.workspace_id,
                payload.source_key,
                decision.value,
                selected.strategy_key if selected else "none",
                f"{confidence:.4f}",
                f"{recommended_weight:.4f}",
            ])
            record = TradingDecisionRecord(
                workspace_id=payload.workspace_id,
                owner_id=payload.owner_id,
                source_key=payload.source_key,
                account_profile=payload.account_profile,
                symbol=payload.symbol,
                timeframe=payload.timeframe,
                decision=decision,
                selected_strategy_key=selected.strategy_key if selected else None,
                recommended_weight=round(recommended_weight, 2),
                confidence=round(confidence, 2),
                quality_score=round(quality, 2),
                stability_score=round(stability, 2),
                explainability_score=round(explainability, 2),
                consistency_score=round(consistency, 2),
                risk_state=payload.risk_state,
                portfolio_state=payload.portfolio_state,
                reasons=reasons,
                trace=trace,
                decision_hash=sha256(raw_hash.encode("utf-8")).hexdigest(),
                created_at=self._now(),
            )
            self._records[record.id] = record
            return record

    def list_records(self, workspace_id: str) -> list[TradingDecisionRecord]:
        with self._lock:
            return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> TradingDecisionRecord | None:
        with self._lock:
            item = self._records.get(record_id)
            return item if item is not None and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> TradingDecisionStatusResponse:
        records = self.list_records(workspace_id)
        return TradingDecisionStatusResponse(
            decisions=len(records),
            approved_recommendations=sum(item.decision == TradingDecision.approve for item in records),
            restrictive_decisions=sum(item.decision in {TradingDecision.reduce, TradingDecision.delay, TradingDecision.shadow, TradingDecision.freeze, TradingDecision.reject} for item in records),
        )


trading_decision_orchestration_service = TradingDecisionOrchestrationService()
