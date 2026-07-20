from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    LifecycleScores,
    LifecycleState,
    LifecycleStatusResponse,
    PerformanceAttribution,
    StrategyLifecycleAssessment,
    StrategyLifecycleAssessmentCreate,
)


class ExecutiveLiveStrategyPerformanceLifecycleService:
    def __init__(self) -> None:
        self._records: dict[UUID, StrategyLifecycleAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: StrategyLifecycleAssessmentCreate) -> StrategyLifecycleAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate strategy lifecycle source key")

        strategy = payload.strategy
        capital = strategy.allocated_capital
        gross_return = strategy.gross_pnl / capital
        net_pnl = strategy.gross_pnl - strategy.trading_costs
        net_return = net_pnl / capital
        benchmark_return = strategy.benchmark_pnl / capital
        alpha_return = net_return - benchmark_return
        cost_drag = strategy.trading_costs / capital
        risk_adjusted_alpha = alpha_return / max(strategy.max_drawdown_share, 0.01)

        policy = payload.policy
        evidence_score = min(100, round(100 * strategy.sample_trades / policy.minimum_sample_trades))
        drawdown_score = max(0, round(100 * (1 - strategy.max_drawdown_share / policy.maximum_drawdown_share)))
        cost_score = max(0, round(100 * (1 - min(1.0, cost_drag / max(abs(gross_return), 0.01)))))
        alpha_score = max(0, min(100, round(50 + risk_adjusted_alpha * 25)))
        regime_score = strategy.regime_fit_score
        confidence = round(
            (
                alpha_score
                + cost_score
                + drawdown_score
                + evidence_score
                + regime_score
                + strategy.execution_quality_score
            )
            / 6
        )

        reasons: list[str] = []
        hard_block = not payload.risk_brain_clear
        if hard_block:
            state = LifecycleState.blocked
            action = "block"
            reasons.append("Risk Brain is not clear for lifecycle action")
        elif payload.consecutive_failed_reviews >= policy.retire_after_consecutive_failures:
            state = LifecycleState.retire
            action = "retire"
            reasons.append("Consecutive failed reviews reached retirement threshold")
        elif strategy.max_drawdown_share > policy.maximum_drawdown_share:
            state = LifecycleState.pause
            action = "pause"
            reasons.append("Strategy drawdown exceeds lifecycle policy")
        elif strategy.risk_share > policy.maximum_risk_share:
            state = LifecycleState.constrain
            action = "reduce-risk"
            reasons.append("Strategy risk share exceeds lifecycle policy")
        elif strategy.sample_trades < policy.minimum_sample_trades:
            state = LifecycleState.observe
            action = "collect-evidence"
            reasons.append("Trade sample is below validation threshold")
        elif (
            strategy.profit_factor < policy.minimum_profit_factor
            or strategy.regime_fit_score < policy.minimum_regime_fit_score
            or strategy.execution_quality_score < policy.minimum_execution_quality_score
            or alpha_return <= 0
        ):
            state = LifecycleState.validate
            action = "validate"
            reasons.append("Strategy requires further validation before promotion")
        else:
            state = LifecycleState.promote
            action = "promote"
            reasons.append("Positive attributable alpha and lifecycle gates are satisfied")

        deployable = payload.human_approved and not hard_block and state in {
            LifecycleState.promote,
            LifecycleState.constrain,
            LifecycleState.pause,
            LifecycleState.retire,
        }
        if not payload.human_approved and not hard_block:
            reasons.append("Human approval is required before lifecycle action")

        record = StrategyLifecycleAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            strategy_id=strategy.strategy_id,
            state=state,
            attribution=PerformanceAttribution(
                gross_return_share=round(gross_return, 6),
                net_return_share=round(net_return, 6),
                benchmark_return_share=round(benchmark_return, 6),
                alpha_return_share=round(alpha_return, 6),
                cost_drag_share=round(cost_drag, 6),
                risk_adjusted_alpha=round(risk_adjusted_alpha, 4),
            ),
            scores=LifecycleScores(
                alpha_quality=alpha_score,
                cost_efficiency=cost_score,
                drawdown_safety=drawdown_score,
                evidence_strength=evidence_score,
                regime_resilience=regime_score,
                lifecycle_confidence=confidence,
            ),
            deployable=deployable,
            recommended_action=action,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(
            AuditRecord(
                workspace_id=record.workspace_id,
                assessment_id=record.id,
                actor_id=record.actor_id,
                action="live-strategy-lifecycle-assessed",
            )
        )
        return record

    def list_assessments(self, workspace_id: str) -> list[StrategyLifecycleAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> StrategyLifecycleAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> LifecycleStatusResponse:
        items = self.list_assessments(workspace_id)
        return LifecycleStatusResponse(
            workspace_id=workspace_id,
            assessments=len(items),
            latest_state=items[-1].state if items else None,
        )

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_live_strategy_performance_lifecycle_service = ExecutiveLiveStrategyPerformanceLifecycleService()
