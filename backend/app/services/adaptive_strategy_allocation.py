from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Dict, List
from uuid import uuid4

from app.schemas.adaptive_strategy_allocation import (
    StrategyAllocationAction,
    StrategyAllocationCreate,
    StrategyAllocationRecord,
    StrategyAllocationScores,
    StrategyAllocationState,
    StrategyRecommendation,
)


@dataclass
class AuditEvent:
    record_id: str
    workspace_id: str
    actor: str
    action: str
    operation_id: str
    version: int


class AdaptiveStrategyAllocationService:
    def __init__(self) -> None:
        self._records: Dict[str, StrategyAllocationRecord] = {}
        self._source_keys: Dict[str, str] = {}
        self._operations: set[str] = set()
        self._audit: List[AuditEvent] = []

    def status(self) -> dict:
        return {
            "module": "adaptive-strategy-allocation",
            "version": "21.74",
            "records": len(self._records),
            "risk_brain_authority": "hard-block",
            "allocation_mutation_enabled": False,
            "strategy_activation_enabled": False,
            "execution_enabled": False,
        }

    def create(self, payload: StrategyAllocationCreate) -> StrategyAllocationRecord:
        composite_key = f"{payload.workspace_id}:{payload.source_key}"
        if composite_key in self._source_keys:
            raise ValueError("duplicate source key within workspace")

        scores, recommendations, flags = self._score(payload)
        state = StrategyAllocationState.REVIEW_REQUIRED if flags else StrategyAllocationState.SCORED
        record = StrategyAllocationRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            scores=scores,
            recommendations=recommendations,
            risk_flags=flags,
        )
        self._records[record.record_id] = record
        self._source_keys[composite_key] = record.record_id
        self._audit.append(
            AuditEvent(record.record_id, record.workspace_id, payload.requested_by, "create", composite_key, 1)
        )
        return record

    def list(self, workspace_id: str) -> List[StrategyAllocationRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> StrategyAllocationRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError("record not found")
        return record

    def act(
        self,
        record_id: str,
        workspace_id: str,
        payload: StrategyAllocationAction,
        risk_blocked: bool = False,
    ) -> StrategyAllocationRecord:
        record = self.get(record_id, workspace_id)
        operation_key = f"{workspace_id}:{payload.operation_id}"
        if operation_key in self._operations:
            return record

        if risk_blocked and payload.action in {"approve", "activate", "monitor"}:
            record.state = StrategyAllocationState.BLOCKED
            record.risk_flags = sorted(set(record.risk_flags + ["risk-brain-hard-block"]))
        else:
            transitions = {
                "score": StrategyAllocationState.SCORED,
                "submit-review": StrategyAllocationState.REVIEW_REQUIRED,
                "approve": StrategyAllocationState.APPROVED,
                "activate": StrategyAllocationState.ACTIVE,
                "monitor": StrategyAllocationState.MONITORING,
                "suspend": StrategyAllocationState.SUSPENDED,
                "revoke": StrategyAllocationState.REVOKED,
                "archive": StrategyAllocationState.ARCHIVED,
            }
            if payload.action == "approve":
                record.approved_by = payload.actor
            record.state = transitions[payload.action]

        record.version += 1
        self._operations.add(operation_key)
        self._audit.append(
            AuditEvent(record.record_id, workspace_id, payload.actor, payload.action, payload.operation_id, record.version)
        )
        return record

    def audit(self, workspace_id: str) -> List[dict]:
        return [event.__dict__ for event in self._audit if event.workspace_id == workspace_id]

    def _score(
        self, payload: StrategyAllocationCreate
    ) -> tuple[StrategyAllocationScores, List[StrategyRecommendation], List[str]]:
        raw_weights: List[float] = []
        health_scores: List[float] = []
        regime_scores: List[float] = []
        alpha_scores: List[float] = []
        correlations: List[float] = []
        confidences: List[float] = []
        recommendations: List[StrategyRecommendation] = []
        flags: List[str] = []

        for item in payload.observations:
            risk_adjusted = item.realized_return / max(item.volatility + item.downside_deviation, 0.0001)
            risk_adjusted_score = max(0, min(100, 50 + risk_adjusted * 12))
            drawdown_score = max(0, 100 - item.max_drawdown * 200)
            profit_score = max(0, min(100, item.profit_factor * 35))
            health = max(
                0,
                min(
                    100,
                    risk_adjusted_score * 0.30
                    + drawdown_score * 0.20
                    + profit_score * 0.20
                    + item.win_rate * 100 * 0.15
                    + item.liquidity_score * 100 * 0.15,
                ),
            )
            alpha_decay = max(0, min(100, (1 - item.alpha_persistence) * 100))
            confidence = item.confidence * item.freshness
            correlation_penalty = max(0, item.average_correlation) * 35
            turnover_penalty = min(item.turnover_rate, 2) * 10
            allocation_score = max(
                0,
                health * 0.35
                + item.regime_fit * 100 * 0.25
                + item.alpha_persistence * 100 * 0.20
                + item.liquidity_score * 100 * 0.10
                + confidence * 100 * 0.10
                - correlation_penalty
                - turnover_penalty,
            )
            raw_weights.append(allocation_score)
            health_scores.append(health)
            regime_scores.append(item.regime_fit * 100)
            alpha_scores.append(item.alpha_persistence * 100)
            correlations.append(item.average_correlation)
            confidences.append(confidence)

            lifecycle = "maintain"
            if alpha_decay >= 60 or health < 40:
                lifecycle = "retirement-candidate"
                flags.append(f"strategy-retirement-candidate:{item.strategy_id}")
            elif health >= 65 and item.alpha_persistence >= 0.65 and item.regime_fit >= 0.65:
                lifecycle = "recovery-or-scale-candidate"
            if item.regime_fit < 0.4:
                flags.append(f"regime-mismatch:{item.strategy_id}")
            if item.average_correlation > 0.8:
                flags.append(f"correlation-alert:{item.strategy_id}")

            recommendations.append(
                StrategyRecommendation(
                    strategy_id=item.strategy_id,
                    health_score=round(health, 2),
                    regime_fit_score=round(item.regime_fit * 100, 2),
                    risk_adjusted_score=round(risk_adjusted_score, 2),
                    alpha_decay_score=round(alpha_decay, 2),
                    recommended_weight=0,
                    lifecycle_signal=lifecycle,
                )
            )

        total_raw = sum(raw_weights)
        normalized = [weight / total_raw if total_raw > 0 else 1 / len(raw_weights) for weight in raw_weights]
        capped = [min(weight, payload.max_strategy_weight) for weight in normalized]
        capped_total = sum(capped)
        final_weights = [weight / capped_total if capped_total > 0 else 1 / len(capped) for weight in capped]

        for recommendation, weight in zip(recommendations, final_weights):
            recommendation.recommended_weight = round(weight, 6)

        current_weights = [item.current_weight for item in payload.observations]
        turnover = sum(abs(target - current) for target, current in zip(final_weights, current_weights)) / 2
        if turnover > payload.max_turnover:
            flags.append("turnover-limit-breach")
        if max(final_weights) > payload.max_strategy_weight + 0.000001:
            flags.append("strategy-weight-cap-breach")

        avg_correlation = mean(correlations)
        diversification = max(0, min(100, 100 - max(avg_correlation, 0) * 75))
        risk_efficiency = max(0, min(100, mean(health_scores) * 0.7 + diversification * 0.3))

        scores = StrategyAllocationScores(
            portfolio_strategy_health=round(mean(health_scores), 2),
            regime_alignment=round(mean(regime_scores), 2),
            diversification_quality=round(diversification, 2),
            alpha_persistence=round(mean(alpha_scores), 2),
            risk_budget_efficiency=round(risk_efficiency, 2),
            turnover_requirement=round(turnover, 6),
            confidence=round(mean(confidences), 4),
        )
        if scores.confidence < 0.6:
            flags.append("low-confidence")
        if scores.portfolio_strategy_health < 45:
            flags.append("portfolio-strategy-health-low")
        if scores.regime_alignment < 50:
            flags.append("portfolio-regime-mismatch")

        return scores, recommendations, sorted(set(flags))


adaptive_strategy_allocation_service = AdaptiveStrategyAllocationService()
