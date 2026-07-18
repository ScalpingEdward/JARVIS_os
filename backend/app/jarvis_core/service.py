from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ApprovalDecision,
    ArbitrationScore,
    AuditRecord,
    CoreAnalysis,
    CoreDecision,
    CoreDecisionCreate,
    CoreStatus,
    DecisionApprovalRequest,
    DecisionConflict,
    DecisionStatus,
    DecisionType,
    ExecutiveRecommendation,
    GoalNode,
    PriorityLevel,
    UnifiedTask,
)


class JarvisCoreService:
    def __init__(self) -> None:
        self._decisions: dict[UUID, CoreDecision] = {}
        self._audit: list[AuditRecord] = []

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _record(self, workspace_id: str, action: str, actor_id: str, decision_id: UUID | None = None, **details) -> None:
        self._audit.append(
            AuditRecord(
                workspace_id=workspace_id,
                action=action,
                actor_id=actor_id,
                decision_id=decision_id,
                details=details,
                created_at=self._now(),
            )
        )

    def status(self, workspace_id: str) -> CoreStatus:
        items = [item for item in self._decisions.values() if item.workspace_id == workspace_id]
        return CoreStatus(
            decisions=len(items),
            analyzed=sum(item.analysis is not None for item in items),
            pending_approval=sum(item.status == DecisionStatus.pending_approval for item in items),
            approved=sum(item.status == DecisionStatus.approved for item in items),
            rejected=sum(item.status == DecisionStatus.rejected for item in items),
            conflicts=sum(len(item.analysis.conflicts) for item in items if item.analysis),
        )

    def create(self, payload: CoreDecisionCreate) -> CoreDecision:
        now = self._now()
        decision = CoreDecision(**payload.model_dump(), created_at=now, updated_at=now)
        self._decisions[decision.id] = decision
        self._record(payload.workspace_id, "core-decision-created", payload.owner_id, decision.id)
        return decision

    def list_decisions(self, workspace_id: str) -> list[CoreDecision]:
        return sorted(
            [item for item in self._decisions.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def get(self, decision_id: UUID, workspace_id: str) -> CoreDecision | None:
        item = self._decisions.get(decision_id)
        return item if item and item.workspace_id == workspace_id else None

    @staticmethod
    def _priority(score: float) -> PriorityLevel:
        if score >= 0.85:
            return PriorityLevel.critical
        if score >= 0.68:
            return PriorityLevel.high
        if score >= 0.45:
            return PriorityLevel.medium
        return PriorityLevel.low

    def analyze(self, decision_id: UUID, workspace_id: str, actor_id: str) -> CoreDecision | None:
        decision = self.get(decision_id, workspace_id)
        if decision is None:
            return None

        capabilities = set(decision.available_capabilities)
        reference_ids = {signal.reference_id for signal in decision.signals}
        scores: list[ArbitrationScore] = []
        conflicts: list[DecisionConflict] = []
        dependency_users: dict[str, list[str]] = defaultdict(list)

        for signal in decision.signals:
            missing_dependencies = [ref for ref in signal.dependencies if ref not in reference_ids]
            missing_capabilities = [cap for cap in signal.required_capabilities if cap not in capabilities]
            dependency_penalty = min(0.35, 0.12 * len(missing_dependencies))
            capability_penalty = min(0.35, 0.12 * len(missing_capabilities))
            risk_penalty = signal.risk * 0.18
            total = (
                signal.urgency * 0.30
                + signal.expected_value * 0.30
                + signal.confidence * 0.25
                + (1 - signal.risk) * 0.15
                - dependency_penalty
                - capability_penalty
            )
            explanation = [
                f"Urgency contribution: {signal.urgency * 0.30:.3f}",
                f"Expected-value contribution: {signal.expected_value * 0.30:.3f}",
                f"Confidence contribution: {signal.confidence * 0.25:.3f}",
                f"Risk penalty: {risk_penalty:.3f}",
            ]
            if missing_dependencies:
                explanation.append(f"Missing dependencies: {', '.join(missing_dependencies)}")
            if missing_capabilities:
                explanation.append(f"Missing capabilities: {', '.join(missing_capabilities)}")
            scores.append(
                ArbitrationScore(
                    reference_id=signal.reference_id,
                    module=signal.module,
                    priority_score=round(total, 4),
                    urgency_score=signal.urgency,
                    value_score=signal.expected_value,
                    confidence_score=signal.confidence,
                    risk_penalty=round(risk_penalty, 4),
                    dependency_penalty=round(dependency_penalty, 4),
                    capability_penalty=round(capability_penalty, 4),
                    total_score=round(total, 4),
                    rank=0,
                    explanation=explanation,
                )
            )
            for dependency in signal.dependencies:
                dependency_users[dependency].append(signal.reference_id)

        scores.sort(key=lambda item: item.total_score, reverse=True)
        scores = [item.model_copy(update={"rank": index}) for index, item in enumerate(scores, start=1)]

        for dependency, users in dependency_users.items():
            if dependency not in reference_ids:
                conflicts.append(
                    DecisionConflict(
                        key=f"missing-dependency:{dependency}",
                        reference_ids=users,
                        severity=PriorityLevel.high,
                        explanation=f"Required dependency {dependency} is absent from the decision context.",
                        resolution="Add the dependency signal or defer affected work before approval.",
                    )
                )

        resource_groups: dict[str, list[str]] = defaultdict(list)
        for signal in decision.signals:
            for capability in signal.required_capabilities:
                resource_groups[capability].append(signal.reference_id)
        for capability, users in resource_groups.items():
            if len(users) > decision.max_parallel_actions:
                conflicts.append(
                    DecisionConflict(
                        key=f"capacity:{capability}",
                        reference_ids=users,
                        severity=PriorityLevel.critical,
                        explanation=f"Capability {capability} is requested by {len(users)} signals, above the parallel limit.",
                        resolution="Sequence the affected work or increase approved capacity.",
                    )
                )

        selected = scores[: decision.max_parallel_actions]
        selected_refs = {item.reference_id for item in selected}
        signal_map = {signal.reference_id: signal for signal in decision.signals}
        tasks: list[UnifiedTask] = []
        for index, score in enumerate(scores, start=1):
            signal = signal_map[score.reference_id]
            missing_dependencies = [ref for ref in signal.dependencies if ref not in reference_ids]
            missing_capabilities = [cap for cap in signal.required_capabilities if cap not in capabilities]
            block_reasons = []
            if missing_dependencies:
                block_reasons.append(f"Missing dependencies: {', '.join(missing_dependencies)}")
            if missing_capabilities:
                block_reasons.append(f"Missing capabilities: {', '.join(missing_capabilities)}")
            tasks.append(
                UnifiedTask(
                    task_key=f"core-{index}-{signal.reference_id}",
                    source_reference_id=signal.reference_id,
                    module=signal.module,
                    sequence=index,
                    priority=self._priority(score.total_score),
                    dependencies=signal.dependencies,
                    required_capabilities=signal.required_capabilities,
                    blocked=bool(block_reasons),
                    block_reasons=block_reasons,
                )
            )

        goals = [
            GoalNode(
                key="objective",
                title=decision.objective,
                priority=PriorityLevel.critical,
                source_references=[signal.reference_id for signal in decision.signals],
            )
        ]
        for score in scores:
            goals.append(
                GoalNode(
                    key=f"goal:{score.reference_id}",
                    title=signal_map[score.reference_id].summary,
                    parent_key="objective",
                    priority=self._priority(score.total_score),
                    source_references=[score.reference_id],
                )
            )

        recommendations: list[ExecutiveRecommendation] = []
        if conflicts:
            recommendations.append(
                ExecutiveRecommendation(
                    decision_type=DecisionType.resolve_conflict,
                    title="Resolve cross-module execution conflicts",
                    rationale=f"{len(conflicts)} conflict(s) must be cleared before controlled execution.",
                    affected_references=sorted({ref for conflict in conflicts for ref in conflict.reference_ids}),
                    confidence=0.95,
                )
            )
        if selected:
            recommendations.append(
                ExecutiveRecommendation(
                    decision_type=DecisionType.prioritize,
                    title="Prioritize highest-value governed signals",
                    rationale="The selected sequence maximizes urgency, value and confidence while penalizing risk and missing prerequisites.",
                    affected_references=[item.reference_id for item in selected],
                    confidence=round(sum(item.confidence_score for item in selected) / len(selected), 4),
                )
            )
        deferred = [item.reference_id for item in scores if item.reference_id not in selected_refs]
        if deferred:
            recommendations.append(
                ExecutiveRecommendation(
                    decision_type=DecisionType.defer,
                    title="Defer lower-ranked work",
                    rationale="Parallel work is constrained by the governed execution limit.",
                    affected_references=deferred,
                    confidence=0.9,
                )
            )

        unblocked = [task for task in tasks if not task.blocked]
        global_confidence = round(
            (sum(item.confidence_score for item in scores) / len(scores)) * (len(unblocked) / len(tasks)), 4
        )
        decision.analysis = CoreAnalysis(
            analyzed_at=self._now(),
            decomposed_goals=goals,
            arbitration=scores,
            conflicts=conflicts,
            unified_task_graph=tasks,
            recommended_sequence=[item.reference_id for item in selected if not next(task for task in tasks if task.source_reference_id == item.reference_id).blocked],
            deferred_references=deferred,
            executive_recommendations=recommendations,
            global_confidence=global_confidence,
            decision_summary=f"Analyzed {len(scores)} cross-module signals; {len(unblocked)} are execution-ready and {len(conflicts)} conflict(s) require governance.",
        )
        decision.status = DecisionStatus.pending_approval
        decision.updated_at = self._now()
        self._record(workspace_id, "core-decision-analyzed", actor_id, decision.id, conflicts=len(conflicts))
        return decision

    def approve(self, decision_id: UUID, payload: DecisionApprovalRequest) -> CoreDecision | None:
        decision = self.get(decision_id, payload.workspace_id)
        if decision is None:
            return None
        if decision.analysis is None:
            raise ValueError("Decision must be analyzed before approval")
        if payload.reviewer_id == decision.owner_id:
            raise ValueError("Decision owners cannot approve their own decisions")
        decision.status = DecisionStatus.approved if payload.decision == ApprovalDecision.approve else DecisionStatus.rejected
        decision.approved_by = payload.reviewer_id
        decision.approval_reason = payload.reason
        decision.updated_at = self._now()
        self._record(payload.workspace_id, f"core-decision-{payload.decision.value}", payload.reviewer_id, decision.id)
        return decision

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


jarvis_core_service = JarvisCoreService()
