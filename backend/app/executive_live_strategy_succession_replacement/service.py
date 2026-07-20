from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    SuccessionAssessment,
    SuccessionAssessmentCreate,
    SuccessionScores,
    SuccessionState,
    SuccessionStatusResponse,
)


class ExecutiveLiveStrategySuccessionReplacementService:
    def __init__(self) -> None:
        self._records: dict[UUID, SuccessionAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: SuccessionAssessmentCreate) -> SuccessionAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate succession source key")

        candidate = payload.candidate
        policy = payload.policy
        reasons: list[str] = []

        if candidate is None:
            evidence = performance = drawdown = diversification = operational = confidence = 0
        else:
            evidence = min(100, round(100 * candidate.evidence_trades / policy.minimum_evidence_trades))
            performance = max(0, min(100, round(50 + (candidate.profit_factor - 1) * 50)))
            drawdown = max(0, round(100 * (1 - candidate.max_drawdown_share / policy.maximum_drawdown_share)))
            diversification = max(0, round(100 * (1 - abs(candidate.correlation_to_retired_strategy))))
            operational = candidate.operational_readiness_score
            confidence = round((evidence + performance + drawdown + candidate.regime_fit_score + candidate.execution_quality_score + operational) / 6)

        if not payload.risk_brain_clear:
            state = SuccessionState.blocked
            action = "block-succession"
            reasons.append("Risk Brain is not clear for succession planning")
        elif payload.retirement_state not in {"archive", "retire"}:
            state = SuccessionState.blocked
            action = "complete-retirement-review"
            reasons.append("Predecessor strategy is not approved for archive or retirement")
        elif not payload.archive_complete:
            state = SuccessionState.preserve_capital
            action = "complete-knowledge-archive"
            reasons.append("Knowledge archive must be complete before succession")
        elif candidate is None:
            state = SuccessionState.preserve_capital
            action = "source-replacement-candidate"
            reasons.append("Released capital remains protected until a candidate exists")
        elif candidate.evidence_trades < policy.minimum_evidence_trades:
            state = SuccessionState.observe_candidate
            action = "collect-candidate-evidence"
            reasons.append("Candidate evidence sample is below policy threshold")
        elif (
            candidate.profit_factor < policy.minimum_profit_factor
            or candidate.max_drawdown_share > policy.maximum_drawdown_share
            or candidate.regime_fit_score < policy.minimum_regime_fit_score
            or candidate.execution_quality_score < policy.minimum_execution_quality_score
            or candidate.operational_readiness_score < policy.minimum_operational_readiness_score
            or abs(candidate.correlation_to_retired_strategy) > policy.maximum_absolute_correlation
        ):
            state = SuccessionState.validate_candidate
            action = "validate-replacement-candidate"
            reasons.append("Candidate does not yet satisfy all replacement gates")
        else:
            state = SuccessionState.succession_ready
            action = "approve-controlled-succession"
            reasons.append("Candidate satisfies evidence, risk, diversification and readiness gates")

        approved_capital = 0.0
        deployable = payload.human_approved and state == SuccessionState.succession_ready and payload.risk_brain_clear
        if deployable:
            approved_capital = round(payload.released_capital * policy.maximum_replacement_capital_share, 2)
        elif state != SuccessionState.blocked and not payload.human_approved:
            reasons.append("Human approval is required before succession capital is deployable")

        record = SuccessionAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            retired_strategy_id=payload.retired_strategy_id,
            candidate_strategy_id=candidate.strategy_id if candidate else None,
            state=state,
            deployable=deployable,
            recommended_action=action,
            approved_capital=approved_capital,
            scores=SuccessionScores(
                evidence_strength=evidence,
                performance_quality=performance,
                drawdown_safety=drawdown,
                diversification_value=diversification,
                operational_readiness=operational,
                succession_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, assessment_id=record.id, actor_id=record.actor_id, action=f"strategy-succession:{record.state.value}"))
        return record

    def status(self, workspace_id: str) -> SuccessionStatusResponse:
        records = self.list_assessments(workspace_id)
        return SuccessionStatusResponse(workspace_id=workspace_id, assessments=len(records), latest_state=records[-1].state if records else None)

    def list_assessments(self, workspace_id: str) -> list[SuccessionAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> SuccessionAssessment | None:
        record = self._records.get(assessment_id)
        return record if record and record.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


executive_live_strategy_succession_replacement_service = ExecutiveLiveStrategySuccessionReplacementService()
