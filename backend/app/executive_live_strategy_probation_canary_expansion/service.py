from __future__ import annotations

from uuid import UUID

from .models import AuditRecord, ProbationAssessment, ProbationAssessmentCreate, ProbationScores, ProbationState, ProbationStatusResponse


class ExecutiveLiveStrategyProbationCanaryExpansionService:
    def __init__(self) -> None:
        self._records: dict[UUID, ProbationAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: ProbationAssessmentCreate) -> ProbationAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate probation source key")

        p, policy = payload.performance, payload.policy
        evidence = min(100, round(50 * p.live_trades / policy.minimum_live_trades + 50 * p.live_days / policy.minimum_live_days))
        performance = max(0, min(100, round(50 + (p.profit_factor - 1) * 50)))
        drawdown = max(0, min(100, round(100 * (1 - p.max_drawdown_share / policy.maximum_drawdown_share))))
        execution = max(0, min(100, round(100 - (p.slippage_bps / max(policy.maximum_slippage_bps, 1) * 50) - (p.execution_error_rate / max(policy.maximum_execution_error_rate, .001) * 50))))
        confidence = round((evidence + performance + drawdown + execution + p.regime_coverage_score + p.operational_stability_score) / 6)
        reasons: list[str] = []

        gates = (
            p.live_trades >= policy.minimum_live_trades,
            p.live_days >= policy.minimum_live_days,
            p.profit_factor >= policy.minimum_profit_factor,
            p.max_drawdown_share <= policy.maximum_drawdown_share,
            p.slippage_bps <= policy.maximum_slippage_bps,
            p.execution_error_rate <= policy.maximum_execution_error_rate,
            p.regime_coverage_score >= policy.minimum_regime_coverage_score,
            p.operational_stability_score >= policy.minimum_operational_stability_score,
        )

        if not payload.risk_brain_clear or p.incidents > 0:
            state, action = ProbationState.blocked, "block-and-investigate"
            reasons.append("Risk Brain or active incidents block canary expansion")
        elif payload.succession_state != "succession-ready":
            state, action = ProbationState.blocked, "complete-succession-governance"
            reasons.append("Strategy is not succession-ready")
        elif p.live_trades < policy.minimum_live_trades or p.live_days < policy.minimum_live_days:
            state, action = ProbationState.hold_canary, "continue-canary-observation"
            reasons.append("Minimum live evidence is not complete")
        elif not all(gates):
            state, action = ProbationState.extend_probation, "remediate-probation-gaps"
            reasons.append("One or more live probation gates failed")
        elif payload.current_deployed_capital < payload.approved_succession_capital * policy.graduation_capital_share:
            state, action = ProbationState.expand_controlled, "approve-one-expansion-step"
            reasons.append("Canary gates passed; one controlled expansion step is eligible")
        else:
            state, action = ProbationState.graduate, "graduate-from-probation"
            reasons.append("Live probation and controlled expansion requirements are satisfied")

        target_share = policy.canary_capital_share
        if state == ProbationState.expand_controlled:
            target_share = min(policy.graduation_capital_share, payload.current_deployed_capital / payload.approved_succession_capital + policy.expansion_step_share)
        elif state == ProbationState.graduate:
            target_share = policy.graduation_capital_share
        approved_total = round(payload.approved_succession_capital * target_share, 2)
        incremental = max(0.0, round(approved_total - payload.current_deployed_capital, 2))
        deployable = payload.human_approved and payload.risk_brain_clear and state in {ProbationState.expand_controlled, ProbationState.graduate}
        if not deployable:
            incremental = 0.0
            if state not in {ProbationState.blocked} and not payload.human_approved:
                reasons.append("Human approval is required before additional capital is deployable")

        record = ProbationAssessment(workspace_id=payload.workspace_id, source_key=payload.source_key, actor_id=payload.actor_id, strategy_id=payload.strategy_id, state=state, deployable=deployable, recommended_action=action, approved_total_capital=approved_total, incremental_capital=incremental, scores=ProbationScores(evidence_maturity=evidence, performance_quality=performance, drawdown_safety=drawdown, execution_quality=execution, regime_coverage=p.regime_coverage_score, operational_stability=p.operational_stability_score, graduation_confidence=confidence), reasons=reasons)
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, assessment_id=record.id, actor_id=record.actor_id, action=f"strategy-probation:{record.state.value}"))
        return record

    def status(self, workspace_id: str) -> ProbationStatusResponse:
        records = self.list_assessments(workspace_id)
        return ProbationStatusResponse(workspace_id=workspace_id, assessments=len(records), latest_state=records[-1].state if records else None)

    def list_assessments(self, workspace_id: str) -> list[ProbationAssessment]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> ProbationAssessment | None:
        record = self._records.get(assessment_id)
        return record if record and record.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [r for r in self._audit if r.workspace_id == workspace_id]


executive_live_strategy_probation_canary_expansion_service = ExecutiveLiveStrategyProbationCanaryExpansionService()
