from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean
from uuid import UUID

from .models import (
    AuditRecord,
    DriftRecord,
    ExperienceCreate,
    ExperienceRecord,
    ExperienceType,
    ImprovementCreate,
    ImprovementRecord,
    LearningRecommendation,
    LearningStatus,
    MetricDelta,
    OutcomeCreate,
    OutcomeRecord,
    OutcomeStatus,
    PatternKind,
    PatternRecord,
    RecommendationReview,
    RecommendationState,
)


class ContinuousLearningService:
    def __init__(self) -> None:
        self.experiences: dict[UUID, ExperienceRecord] = {}
        self.outcomes: dict[UUID, OutcomeRecord] = {}
        self.patterns: dict[UUID, PatternRecord] = {}
        self.recommendations: dict[UUID, LearningRecommendation] = {}
        self.improvements: dict[UUID, ImprovementRecord] = {}
        self.audit_records: list[AuditRecord] = []

    def reset(self) -> None:
        self.experiences.clear()
        self.outcomes.clear()
        self.patterns.clear()
        self.recommendations.clear()
        self.improvements.clear()
        self.audit_records.clear()

    def create_experience(self, payload: ExperienceCreate) -> ExperienceRecord:
        duplicate = any(
            item.workspace_id == payload.workspace_id and item.key == payload.key
            for item in self.experiences.values()
        )
        if duplicate:
            raise ValueError("experience key already exists in workspace")
        record = ExperienceRecord(
            **payload.model_dump(exclude={"human_approved", "automatic_external_action"})
        )
        self.experiences[record.id] = record
        self._audit(record.workspace_id, record.owner_id, "experience.created", "experience", record.id, {"key": record.key})
        return record

    def list_experiences(self, workspace_id: str) -> list[ExperienceRecord]:
        return sorted(
            [item for item in self.experiences.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def get_experience(self, workspace_id: str, experience_id: UUID) -> ExperienceRecord | None:
        record = self.experiences.get(experience_id)
        return record if record and record.workspace_id == workspace_id else None

    def create_outcome(self, payload: OutcomeCreate) -> OutcomeRecord:
        experience = self.get_experience(payload.workspace_id, payload.experience_id)
        if experience is None:
            raise ValueError("experience not found in workspace")
        deltas = self._metric_deltas(experience, payload)
        record = OutcomeRecord(
            **payload.model_dump(exclude={"human_approved", "automatic_external_action"}),
            metric_deltas=deltas,
        )
        self.outcomes[record.id] = record
        self._audit(record.workspace_id, record.actor_id, "outcome.created", "outcome", record.id, {"status": record.status.value})
        self.refresh_learning(record.workspace_id, record.actor_id)
        return record

    def list_outcomes(self, workspace_id: str) -> list[OutcomeRecord]:
        return sorted(
            [item for item in self.outcomes.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def refresh_learning(self, workspace_id: str, actor_id: str) -> None:
        for pattern_id in [key for key, value in self.patterns.items() if value.workspace_id == workspace_id]:
            del self.patterns[pattern_id]
        for recommendation_id in [key for key, value in self.recommendations.items() if value.workspace_id == workspace_id and value.state == RecommendationState.PROPOSED]:
            del self.recommendations[recommendation_id]
        outcomes = self.list_outcomes(workspace_id)
        if not outcomes:
            return
        self._discover_status_patterns(workspace_id, outcomes)
        self._discover_root_cause_patterns(workspace_id, outcomes)
        self._discover_metric_patterns(workspace_id, outcomes)
        self._generate_recommendations(workspace_id)
        self._audit(workspace_id, actor_id, "learning.refreshed", "workspace", None, {"outcomes": len(outcomes)})

    def list_patterns(self, workspace_id: str) -> list[PatternRecord]:
        return sorted(
            [item for item in self.patterns.values() if item.workspace_id == workspace_id],
            key=lambda item: (-item.confidence, -item.support_count, item.key),
        )

    def list_recommendations(self, workspace_id: str) -> list[LearningRecommendation]:
        return sorted(
            [item for item in self.recommendations.values() if item.workspace_id == workspace_id],
            key=lambda item: (-item.confidence, item.key),
        )

    def review_recommendation(self, recommendation_id: UUID, payload: RecommendationReview) -> LearningRecommendation:
        record = self.recommendations.get(recommendation_id)
        if record is None or record.workspace_id != payload.workspace_id:
            raise ValueError("recommendation not found")
        record.state = RecommendationState.APPROVED if payload.approve else RecommendationState.REJECTED
        record.reviewed_by = payload.reviewer_id
        self._audit(record.workspace_id, payload.reviewer_id, "recommendation.reviewed", "recommendation", record.id, {"approved": payload.approve})
        return record

    def create_improvement(self, payload: ImprovementCreate) -> ImprovementRecord:
        recommendation = self.recommendations.get(payload.recommendation_id)
        if recommendation is None or recommendation.workspace_id != payload.workspace_id:
            raise ValueError("recommendation not found")
        if recommendation.state != RecommendationState.APPROVED:
            raise ValueError("recommendation must be approved before improvement tracking")
        if any(item.recommendation_id == payload.recommendation_id for item in self.improvements.values()):
            raise ValueError("improvement already exists for recommendation")
        record = ImprovementRecord(**payload.model_dump())
        self.improvements[record.id] = record
        self._audit(record.workspace_id, record.owner_id, "improvement.created", "improvement", record.id, {})
        return record

    def list_improvements(self, workspace_id: str) -> list[ImprovementRecord]:
        return sorted(
            [item for item in self.improvements.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def drift(self, workspace_id: str, minimum_samples: int = 4) -> list[DriftRecord]:
        values: dict[str, list[float]] = defaultdict(list)
        for outcome in reversed(self.list_outcomes(workspace_id)):
            for metric in outcome.actual_metrics:
                values[metric.key].append(metric.value)
        records: list[DriftRecord] = []
        for key, samples in values.items():
            if len(samples) < minimum_samples:
                continue
            split = len(samples) // 2
            baseline = mean(samples[:split])
            recent = mean(samples[split:])
            change = recent - baseline
            pct = None if baseline == 0 else (change / abs(baseline)) * 100
            magnitude = abs(pct or change)
            severity = "critical" if magnitude >= 30 else "warning" if magnitude >= 15 else "info"
            records.append(
                DriftRecord(
                    metric_key=key,
                    baseline_mean=round(baseline, 4),
                    recent_mean=round(recent, 4),
                    absolute_change=round(change, 4),
                    percentage_change=round(pct, 4) if pct is not None else None,
                    severity=severity,
                    sample_size=len(samples),
                )
            )
        return sorted(records, key=lambda item: ({"critical": 0, "warning": 1, "info": 2}[item.severity], item.metric_key))

    def status(self, workspace_id: str) -> LearningStatus:
        return LearningStatus(
            experiences=sum(item.workspace_id == workspace_id for item in self.experiences.values()),
            outcomes=sum(item.workspace_id == workspace_id for item in self.outcomes.values()),
            patterns=sum(item.workspace_id == workspace_id for item in self.patterns.values()),
            recommendations=sum(item.workspace_id == workspace_id for item in self.recommendations.values()),
            open_improvements=sum(item.workspace_id == workspace_id and item.state.value == "open" for item in self.improvements.values()),
        )

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit_records if item.workspace_id == workspace_id]

    @staticmethod
    def _metric_deltas(experience: ExperienceRecord, payload: OutcomeCreate) -> list[MetricDelta]:
        expected = {item.key: item.value for item in experience.expected_metrics}
        actual = {item.key: item.value for item in payload.actual_metrics}
        deltas: list[MetricDelta] = []
        for key in sorted(set(expected) | set(actual)):
            exp = expected.get(key)
            act = actual.get(key)
            absolute = None if exp is None or act is None else act - exp
            percentage = None if absolute is None or exp == 0 else (absolute / abs(exp)) * 100
            deltas.append(
                MetricDelta(
                    key=key,
                    expected=exp,
                    actual=act,
                    absolute_delta=round(absolute, 4) if absolute is not None else None,
                    percentage_delta=round(percentage, 4) if percentage is not None else None,
                )
            )
        return deltas

    def _discover_status_patterns(self, workspace_id: str, outcomes: list[OutcomeRecord]) -> None:
        counts = Counter(item.status for item in outcomes)
        total = len(outcomes)
        for status, count in counts.items():
            if count < 2:
                continue
            kind = PatternKind.SUCCESS if status == OutcomeStatus.SUCCESS else PatternKind.FAILURE if status == OutcomeStatus.FAILURE else PatternKind.PERFORMANCE
            self._store_pattern(
                workspace_id,
                kind,
                f"status.{status.value}",
                f"Repeated {status.value} outcomes",
                f"{count} of {total} recorded outcomes have status {status.value}.",
                count,
                min(1.0, count / max(2, total)),
                [item.experience_id for item in outcomes if item.status == status],
                [f"status={status.value}"],
            )

    def _discover_root_cause_patterns(self, workspace_id: str, outcomes: list[OutcomeRecord]) -> None:
        causes: dict[str, list[UUID]] = defaultdict(list)
        for outcome in outcomes:
            for cause in outcome.root_causes:
                causes[cause.strip().lower()].append(outcome.experience_id)
        for cause, experience_ids in causes.items():
            if len(experience_ids) < 2:
                continue
            self._store_pattern(
                workspace_id,
                PatternKind.FAILURE,
                f"cause.{self._slug(cause)}",
                f"Recurring root cause: {cause}",
                "The same root cause appears across multiple recorded outcomes.",
                len(experience_ids),
                min(1.0, 0.5 + 0.1 * len(experience_ids)),
                experience_ids,
                [cause],
            )

    def _discover_metric_patterns(self, workspace_id: str, outcomes: list[OutcomeRecord]) -> None:
        deltas: dict[str, list[float]] = defaultdict(list)
        experience_ids: dict[str, list[UUID]] = defaultdict(list)
        for outcome in outcomes:
            for delta in outcome.metric_deltas:
                if delta.percentage_delta is None:
                    continue
                deltas[delta.key].append(delta.percentage_delta)
                experience_ids[delta.key].append(outcome.experience_id)
        for key, values in deltas.items():
            if len(values) < 2:
                continue
            average = mean(values)
            if abs(average) < 10:
                continue
            kind = PatternKind.SUCCESS if average > 0 else PatternKind.PERFORMANCE
            self._store_pattern(
                workspace_id,
                kind,
                f"metric.{key}",
                f"Metric trend: {key}",
                f"Average expected-to-actual variance is {average:.2f}%.",
                len(values),
                min(1.0, 0.5 + abs(average) / 100),
                experience_ids[key],
                [f"average_delta={average:.2f}%"],
            )

    def _generate_recommendations(self, workspace_id: str) -> None:
        for pattern in self.list_patterns(workspace_id):
            if pattern.kind == PatternKind.FAILURE:
                title = f"Reduce recurrence of {pattern.title.lower()}"
                benefit = "Lower failure frequency and improve execution reliability."
            elif pattern.kind == PatternKind.SUCCESS:
                title = f"Standardize {pattern.title.lower()}"
                benefit = "Increase reuse of demonstrated successful behavior."
            else:
                title = f"Review {pattern.title.lower()}"
                benefit = "Improve calibration between planned and actual outcomes."
            target_type = self._target_type(pattern.experience_ids)
            record = LearningRecommendation(
                workspace_id=workspace_id,
                key=f"recommendation.{pattern.key}",
                title=title,
                rationale=[pattern.description, *pattern.evidence],
                target_type=target_type,
                expected_benefit=benefit,
                confidence=pattern.confidence,
                pattern_ids=[pattern.id],
            )
            self.recommendations[record.id] = record

    def _target_type(self, experience_ids: list[UUID]) -> ExperienceType:
        types = [self.experiences[item].experience_type for item in experience_ids if item in self.experiences]
        return Counter(types).most_common(1)[0][0] if types else ExperienceType.MISSION

    def _store_pattern(
        self,
        workspace_id: str,
        kind: PatternKind,
        key: str,
        title: str,
        description: str,
        support_count: int,
        confidence: float,
        experience_ids: list[UUID],
        evidence: list[str],
    ) -> None:
        record = PatternRecord(
            workspace_id=workspace_id,
            kind=kind,
            key=key,
            title=title,
            description=description,
            support_count=support_count,
            confidence=round(confidence, 4),
            experience_ids=list(dict.fromkeys(experience_ids)),
            evidence=evidence,
        )
        self.patterns[record.id] = record

    @staticmethod
    def _slug(value: str) -> str:
        return "-".join("".join(char if char.isalnum() else " " for char in value).split())[:120] or "unknown"

    def _audit(
        self,
        workspace_id: str,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: UUID | None,
        details: dict,
    ) -> None:
        self.audit_records.append(
            AuditRecord(
                workspace_id=workspace_id,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
                created_at=datetime.now(timezone.utc),
            )
        )


continuous_learning_service = ContinuousLearningService()
