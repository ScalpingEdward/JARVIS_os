from datetime import datetime, timezone
from uuid import UUID

from .models import (
    MonteCarloSummary,
    PortfolioOptimizerAudit,
    PortfolioOptimizerCreate,
    PortfolioOptimizerExecuteRequest,
    PortfolioOptimizerRecord,
    PortfolioOptimizerState,
    PortfolioOptimizerStatus,
    StrategyRecommendation,
    StressTestSummary,
)


class AIPortfolioOptimizerService:
    def __init__(self) -> None:
        self._records: dict[UUID, PortfolioOptimizerRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[PortfolioOptimizerAudit] = []

    def create(self, payload: PortfolioOptimizerCreate) -> PortfolioOptimizerRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail, score, cash, recommendations, monte_carlo, stress = self._evaluate(payload)
        record = PortfolioOptimizerRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            portfolio_score=score,
            recommended_cash_pct=cash,
            recommendations=recommendations,
            monte_carlo=monte_carlo,
            stress_test=stress,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: PortfolioOptimizerCreate):
        if payload.upstream_risk_brain_blocked:
            return PortfolioOptimizerState.BLOCKED, "upstream Risk Brain hard block", 0, 100, [], None, None
        if not payload.account_risk_approved or not payload.prop_rules_approved:
            return PortfolioOptimizerState.BLOCKED, "account-risk and prop-rule approval required", 0, 100, [], None, None
        if not payload.market_allowed_by_v19_08:
            return PortfolioOptimizerState.EVIDENCE_REQUIRED, "v19.08 market permission required", 0, 100, [], None, None
        if any(not item.shadow_validated_by_v19_09 or not item.journal_validated_by_v19_10 for item in payload.strategies):
            return PortfolioOptimizerState.EVIDENCE_REQUIRED, "v19.09 shadow and v19.10 journal evidence required", 0, 100, [], None, None

        scored: list[tuple[float, object]] = []
        for item in payload.strategies:
            sample_factor = min(1.0, item.trades / 100)
            risk_penalty = item.max_drawdown_pct * 2.2 + item.ulcer_index * 1.3 + item.volatility_pct * 0.5
            correlation_penalty = max(0.0, item.correlation_to_portfolio) * 15
            quality = (
                item.win_rate_pct * 0.12
                + max(-2.0, min(4.0, item.expectancy_r)) * 10
                + min(item.profit_factor, 3.0) * 8
                + max(-2.0, min(4.0, item.sharpe)) * 5
                + max(-2.0, min(5.0, item.sortino)) * 3
                + min(max(item.recovery_factor, 0), 5) * 4
                + item.stability_score * 0.28
            )
            score = max(0.0, min(100.0, quality * sample_factor - risk_penalty - correlation_penalty + 25))
            scored.append((round(score, 2), item))

        positive_total = sum(max(score, 1.0) for score, _ in scored)
        allocatable = max(0.0, 100.0 - payload.cash_floor_pct)
        recommendations: list[StrategyRecommendation] = []
        raw_weights: list[float] = []
        for score, item in scored:
            weight = allocatable * max(score, 1.0) / positive_total
            weight = min(weight, payload.max_strategy_weight_pct)
            if score < 35:
                weight = 0.0
            raw_weights.append(weight)

        total_weight = sum(raw_weights)
        if total_weight > allocatable and total_weight > 0:
            raw_weights = [weight * allocatable / total_weight for weight in raw_weights]
        recommended_cash = round(100.0 - sum(raw_weights), 2)

        for (score, item), weight in zip(scored, raw_weights):
            weight = round(weight, 2)
            delta = weight - item.current_weight_pct
            if score < 35:
                action = "pause"
                rationale = "risk-adjusted score below minimum allocation threshold"
            elif delta > 3:
                action = "increase"
                rationale = "stronger risk-adjusted performance and diversification contribution"
            elif delta < -3:
                action = "reduce"
                rationale = "allocation exceeds current risk-adjusted contribution"
            else:
                action = "retain"
                rationale = "current allocation is within governed tolerance"
            recommendations.append(StrategyRecommendation(
                strategy_id=item.strategy_id,
                score=score,
                current_weight_pct=item.current_weight_pct,
                recommended_weight_pct=weight,
                action=action,
                rationale=rationale,
            ))

        avg_score = round(sum(score for score, _ in scored) / len(scored), 2)
        worst_stress = max(
            payload.stress.flash_crash_loss_pct,
            payload.stress.spread_explosion_loss_pct,
            payload.stress.liquidity_removal_loss_pct,
            payload.stress.server_delay_loss_pct,
            payload.stress.slippage_loss_pct,
        )
        heat = round(sum(weight * item.volatility_pct / 100 for weight, (_, item) in zip(raw_weights, scored)), 2)
        stress_passed = worst_stress <= payload.max_drawdown_limit_pct and heat <= payload.max_portfolio_heat_pct
        stress = StressTestSummary(
            worst_scenario_loss_pct=round(worst_stress, 2),
            portfolio_heat_pct=heat,
            passed=stress_passed,
        )

        expected = sum(item.expectancy_r * weight / 100 for weight, (_, item) in zip(raw_weights, scored))
        dispersion = sum(item.volatility_pct * weight / 100 for weight, (_, item) in zip(raw_weights, scored))
        ruin = max(0.0, min(100.0, (dispersion - expected * 10) * 2 + worst_stress * 2))
        monte_carlo = MonteCarloSummary(
            runs=payload.monte_carlo_runs,
            worst_case_return_pct=round(expected * 10 - dispersion * 1.5 - worst_stress, 2),
            median_return_pct=round(expected * 10, 2),
            best_case_return_pct=round(expected * 10 + dispersion * 1.5, 2),
            risk_of_ruin_pct=round(ruin, 2),
            estimated_recovery_days=max(0, round(worst_stress * 5 / max(expected, 0.1))),
        )

        if not stress_passed or ruin > 20:
            state = PortfolioOptimizerState.REVIEW_REQUIRED
            detail = "stress or risk-of-ruin threshold requires governed review"
        elif payload.human_approved:
            state = PortfolioOptimizerState.RECOMMENDATION_READY
            detail = "portfolio recommendations ready; no live changes executed"
        else:
            state = PortfolioOptimizerState.APPROVAL_REQUIRED
            detail = "human approval required before recommendation activation"
        return state, detail, avg_score, recommended_cash, recommendations, monte_carlo, stress

    def execute(self, record_id: UUID, workspace_id: str, request: PortfolioOptimizerExecuteRequest) -> PortfolioOptimizerRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("optimizer record not found")
        if request.action == "approve":
            approved = request.human_approved if request.human_approved is not None else record.request.human_approved
            if not approved:
                raise ValueError("human approval required")
            if record.state not in {PortfolioOptimizerState.APPROVAL_REQUIRED, PortfolioOptimizerState.RECOMMENDATION_READY}:
                raise ValueError("approval unavailable from current state")
            record.state = PortfolioOptimizerState.APPROVED
            record.detail = "recommendation package approved for downstream governor review; no live changes executed"
        else:
            record.state = PortfolioOptimizerState.ARCHIVED
            record.detail = "optimizer recommendation archived"
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> PortfolioOptimizerRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[PortfolioOptimizerRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> PortfolioOptimizerStatus:
        records = self.list_records(workspace_id)
        ready = {PortfolioOptimizerState.RECOMMENDATION_READY, PortfolioOptimizerState.APPROVED}
        blocked = {PortfolioOptimizerState.BLOCKED, PortfolioOptimizerState.EVIDENCE_REQUIRED, PortfolioOptimizerState.REVIEW_REQUIRED}
        return PortfolioOptimizerStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            ready_records=sum(record.state in ready for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[PortfolioOptimizerAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: PortfolioOptimizerRecord, actor_id: str, action: str) -> None:
        self._audit.append(PortfolioOptimizerAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


ai_portfolio_optimizer_service = AIPortfolioOptimizerService()
