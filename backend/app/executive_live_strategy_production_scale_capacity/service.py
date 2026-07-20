from __future__ import annotations

from uuid import UUID

from .models import AuditRecord, ProductionScaleAssessment, ProductionScaleAssessmentCreate, ProductionScaleScores, ProductionScaleState, ProductionScaleStatusResponse


class ExecutiveLiveStrategyProductionScaleCapacityService:
    def __init__(self) -> None:
        self._records: dict[UUID, ProductionScaleAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: ProductionScaleAssessmentCreate) -> ProductionScaleAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate production scale source key")

        p, policy = payload.performance, payload.policy
        evidence = min(100, round(50 * p.live_trades / policy.minimum_live_trades + 50 * p.live_days / policy.minimum_live_days))
        performance = max(0, min(100, round(50 + (p.profit_factor - 1) * 50)))
        drawdown = max(0, min(100, round(100 * (1 - p.max_drawdown_share / policy.maximum_drawdown_share))))
        capacity = max(0, min(100, round(100 * (1 - p.capacity_utilization_share / policy.maximum_capacity_utilization_share))))
        execution = max(0, min(100, round((p.fill_quality_score + max(0, 100 - p.slippage_bps / max(policy.maximum_slippage_bps, 1) * 100)) / 2)))
        diversification = max(0, min(100, round(100 * (1 - p.concentration_share / policy.maximum_concentration_share))))
        confidence = round((evidence + performance + drawdown + capacity + execution + p.regime_coverage_score + p.operational_stability_score + diversification) / 8)
        reasons: list[str] = []

        gates = (
            p.live_trades >= policy.minimum_live_trades,
            p.live_days >= policy.minimum_live_days,
            p.profit_factor >= policy.minimum_profit_factor,
            p.max_drawdown_share <= policy.maximum_drawdown_share,
            p.capacity_utilization_share <= policy.maximum_capacity_utilization_share,
            p.slippage_bps <= policy.maximum_slippage_bps,
            p.fill_quality_score >= policy.minimum_fill_quality_score,
            p.regime_coverage_score >= policy.minimum_regime_coverage_score,
            p.operational_stability_score >= policy.minimum_operational_stability_score,
            p.concentration_share <= policy.maximum_concentration_share,
        )

        if not payload.risk_brain_clear or p.active_incidents > 0:
            state, action = ProductionScaleState.blocked, "block-production-scale"
            reasons.append("Risk Brain or active incidents block production scaling")
        elif payload.probation_state != "graduate":
            state, action = ProductionScaleState.blocked, "complete-probation-governance"
            reasons.append("Strategy has not graduated from probation")
        elif p.capacity_utilization_share > policy.maximum_capacity_utilization_share or p.concentration_share > policy.maximum_concentration_share:
            state, action = ProductionScaleState.reduce_exposure, "reduce-capacity-or-concentration"
            reasons.append("Capacity utilization or concentration exceeds production policy")
        elif p.live_trades < policy.minimum_live_trades or p.live_days < policy.minimum_live_days:
            state, action = ProductionScaleState.hold_capacity, "collect-production-evidence"
            reasons.append("Minimum production evidence is incomplete")
        elif not all(gates):
            state, action = ProductionScaleState.hold_capacity, "remediate-production-gaps"
            reasons.append("One or more production scale gates failed")
        elif payload.current_deployed_capital < payload.approved_strategy_capital * policy.maximum_production_capital_share:
            state, action = ProductionScaleState.scale_controlled, "approve-one-production-scale-step"
            reasons.append("Production gates passed; one controlled scale step is eligible")
        else:
            state, action = ProductionScaleState.production_ready, "maintain-production-capacity"
            reasons.append("Strategy satisfies production scale and capacity governance")

        current_share = payload.current_deployed_capital / payload.approved_strategy_capital
        target_share = current_share
        if state == ProductionScaleState.scale_controlled:
            target_share = min(policy.maximum_production_capital_share, current_share + policy.scale_step_share)
        elif state == ProductionScaleState.production_ready:
            target_share = policy.maximum_production_capital_share
        elif state == ProductionScaleState.reduce_exposure:
            target_share = min(current_share, policy.maximum_concentration_share)

        approved_total = round(payload.approved_strategy_capital * target_share, 2)
        incremental = max(0.0, round(approved_total - payload.current_deployed_capital, 2))
        deployable = payload.human_approved and payload.risk_brain_clear and state in {ProductionScaleState.scale_controlled, ProductionScaleState.production_ready}
        if not deployable:
            incremental = 0.0
            if state not in {ProductionScaleState.blocked, ProductionScaleState.reduce_exposure} and not payload.human_approved:
                reasons.append("Human approval is required before additional production capital is deployable")

        record = ProductionScaleAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            strategy_id=payload.strategy_id,
            state=state,
            deployable=deployable,
            recommended_action=action,
            approved_total_capital=approved_total,
            incremental_capital=incremental,
            scores=ProductionScaleScores(
                evidence_maturity=evidence,
                performance_quality=performance,
                drawdown_safety=drawdown,
                capacity_headroom=capacity,
                execution_quality=execution,
                diversification_safety=diversification,
                production_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, assessment_id=record.id, actor_id=record.actor_id, action=f"strategy-production-scale:{record.state.value}"))
        return record

    def status(self, workspace_id: str) -> ProductionScaleStatusResponse:
        records = self.list_assessments(workspace_id)
        return ProductionScaleStatusResponse(workspace_id=workspace_id, assessments=len(records), latest_state=records[-1].state if records else None)

    def list_assessments(self, workspace_id: str) -> list[ProductionScaleAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> ProductionScaleAssessment | None:
        record = self._records.get(assessment_id)
        return record if record and record.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


executive_live_strategy_production_scale_capacity_service = ExecutiveLiveStrategyProductionScaleCapacityService()
