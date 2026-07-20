from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    KnowledgePackage,
    ReviewState,
    ReviewStatusResponse,
    StrategyReviewAssessment,
    StrategyReviewCreate,
)


class ExecutiveLiveStrategyReviewRetirementKnowledgeService:
    def __init__(self) -> None:
        self._records: dict[UUID, StrategyReviewAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: StrategyReviewCreate) -> StrategyReviewAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate strategy review source key")

        strategy = payload.strategy
        policy = payload.policy
        evidence_ready = (
            strategy.evidence_items >= policy.minimum_evidence_items
            and strategy.evidence_completeness_score >= policy.minimum_evidence_completeness_score
        )
        reproducible = strategy.reproducibility_score >= policy.minimum_reproducibility_score
        documented = strategy.documentation_score >= policy.minimum_documentation_score
        dependency_safe = strategy.operational_dependency_score <= policy.maximum_operational_dependency_score
        preservation_score = round(
            (
                strategy.evidence_completeness_score
                + strategy.reproducibility_score
                + strategy.documentation_score
                + (100 - strategy.operational_dependency_score)
            )
            / 4
        )

        required_artifacts: list[str] = []
        if not evidence_ready:
            required_artifacts.append("complete evidence bundle")
        if not reproducible:
            required_artifacts.append("reproducible validation runbook")
        if not documented:
            required_artifacts.append("strategy decision and operating documentation")
        if not dependency_safe:
            required_artifacts.append("dependency removal or replacement plan")
        if strategy.retirement_candidate:
            required_artifacts.extend(["final performance record", "retirement rationale", "rollback-safe archive"])

        reasons: list[str] = []
        if not payload.risk_brain_clear:
            state = ReviewState.blocked
            action = "block-review"
            reasons.append("Risk Brain is not clear for strategy review action")
        elif strategy.active_incidents > 0:
            state = ReviewState.blocked
            action = "resolve-incidents"
            reasons.append("Active incidents must be resolved before review or retirement")
        elif (
            strategy.retirement_candidate
            or strategy.lifecycle_state == "retire"
            or strategy.consecutive_failed_reviews >= policy.retire_after_consecutive_failures
        ):
            if evidence_ready and reproducible and documented:
                state = ReviewState.retire
                action = "retire-and-preserve"
                reasons.append("Retirement criteria are met and the knowledge package is preservation-ready")
            else:
                state = ReviewState.archive
                action = "complete-archive"
                reasons.append("Retirement is indicated but preservation artifacts are incomplete")
        elif strategy.unresolved_findings > 0 or not all((evidence_ready, reproducible, documented, dependency_safe)):
            state = ReviewState.remediate
            action = "remediate-review-gaps"
            reasons.append("Review findings or knowledge-governance gates require remediation")
        else:
            state = ReviewState.retain
            action = "retain"
            reasons.append("Strategy remains supportable, reproducible and adequately documented")

        deployable = payload.human_approved and payload.risk_brain_clear and state in {
            ReviewState.retain,
            ReviewState.archive,
            ReviewState.retire,
        }
        if not payload.human_approved and payload.risk_brain_clear:
            reasons.append("Human approval is required before review action")

        record = StrategyReviewAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            strategy_id=strategy.strategy_id,
            state=state,
            deployable=deployable,
            recommended_action=action,
            reasons=reasons,
            knowledge=KnowledgePackage(
                evidence_ready=evidence_ready,
                reproducible=reproducible,
                documented=documented,
                dependency_safe=dependency_safe,
                preservation_score=preservation_score,
                required_artifacts=required_artifacts,
            ),
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(
            AuditRecord(
                workspace_id=record.workspace_id,
                assessment_id=record.id,
                actor_id=record.actor_id,
                action=f"strategy-review:{record.state.value}",
            )
        )
        return record

    def status(self, workspace_id: str) -> ReviewStatusResponse:
        records = self.list_assessments(workspace_id)
        return ReviewStatusResponse(
            workspace_id=workspace_id,
            assessments=len(records),
            latest_state=records[-1].state if records else None,
        )

    def list_assessments(self, workspace_id: str) -> list[StrategyReviewAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> StrategyReviewAssessment | None:
        record = self._records.get(assessment_id)
        return record if record and record.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


executive_live_strategy_review_retirement_knowledge_service = (
    ExecutiveLiveStrategyReviewRetirementKnowledgeService()
)
