from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from .models import (
    FeedbackSignal,
    RiskPosture,
    ScenarioRequest,
    ScenarioScore,
    TwinFeedback,
    TwinFeedbackCreate,
    TwinProfile,
    TwinProfileCreate,
    TwinRecommendation,
    TwinStatus,
)


class DigitalTwinError(ValueError):
    pass


class DigitalTwinService:
    """Advisory decision model that learns only from explicitly consented feedback."""

    def __init__(self) -> None:
        self._profile: TwinProfile | None = None
        self._recommendations: dict[UUID, TwinRecommendation] = {}
        self._feedback: list[TwinFeedback] = []

    def reset(self) -> None:
        self._profile = None
        self._recommendations.clear()
        self._feedback.clear()

    def configure(self, payload: TwinProfileCreate) -> TwinProfile:
        version = 1 if self._profile is None else self._profile.version + 1
        created_at = datetime.now(timezone.utc) if self._profile is None else self._profile.created_at
        learned = 0 if self._profile is None else self._profile.learned_feedback_count
        self._profile = TwinProfile(
            **payload.model_dump(),
            version=version,
            created_at=created_at,
            updated_at=datetime.now(timezone.utc),
            learned_feedback_count=learned,
        )
        return self.profile()

    def profile(self) -> TwinProfile:
        if self._profile is None:
            raise DigitalTwinError("Digital twin profile is not configured")
        return self._profile.model_copy(deep=True)

    def status(self) -> TwinStatus:
        profile = self._profile
        return TwinStatus(
            configured=profile is not None,
            owner_name=profile.owner_name if profile else "MASTER Brano",
            profile_version=profile.version if profile else 0,
            goals=len(profile.goals) if profile else 0,
            recommendations=len(self._recommendations),
            feedback_items=len(self._feedback),
        )

    def evaluate(self, payload: ScenarioRequest) -> TwinRecommendation:
        profile = self.profile()
        scores = [self._score(profile, option) for option in payload.options]
        scores.sort(key=lambda item: item.score, reverse=True)
        winner = scores[0]
        runner_up = scores[1]
        margin = max(0.0, winner.score - runner_up.score)
        confidence = min(0.99, max(0.35, winner.score * 0.75 + margin * 0.6))
        explanation = (
            f"{profile.owner_name}: '{winner.title}' has the strongest fit with your current goals, "
            f"risk posture and evidence threshold. The recommendation is advisory and requires your approval."
        )
        record = TwinRecommendation(
            profile_id=profile.id,
            question=payload.question,
            recommended_option_id=winner.option_id,
            recommended_title=winner.title,
            confidence=round(confidence, 4),
            explanation=explanation,
            scores=scores,
            requires_human_approval=True,
        )
        self._recommendations[record.id] = record
        return record.model_copy(deep=True)

    def recommendation(self, recommendation_id: UUID) -> TwinRecommendation | None:
        record = self._recommendations.get(recommendation_id)
        return record.model_copy(deep=True) if record else None

    def list_recommendations(self) -> list[TwinRecommendation]:
        return [item.model_copy(deep=True) for item in reversed(list(self._recommendations.values()))]

    def add_feedback(self, payload: TwinFeedbackCreate) -> TwinFeedback:
        recommendation = self._recommendations.get(payload.recommendation_id)
        if recommendation is None:
            raise DigitalTwinError("Recommendation not found")
        if payload.selected_option_id is not None and payload.selected_option_id not in {
            score.option_id for score in recommendation.scores
        }:
            raise DigitalTwinError("Selected option does not belong to the recommendation")
        applied = bool(payload.allow_learning and payload.signal != FeedbackSignal.neutral)
        feedback = TwinFeedback(**payload.model_dump(), applied_to_profile=applied)
        self._feedback.append(feedback)
        if applied:
            self._apply_feedback(payload.signal)
        return feedback.model_copy(deep=True)

    def feedback(self) -> list[TwinFeedback]:
        return [item.model_copy(deep=True) for item in reversed(self._feedback)]

    def _apply_feedback(self, signal: FeedbackSignal) -> None:
        if self._profile is None:
            return
        profile = self._profile
        threshold = profile.evidence_threshold
        if signal == FeedbackSignal.accepted:
            threshold = max(0.5, threshold - 0.01)
        elif signal == FeedbackSignal.rejected:
            threshold = min(0.95, threshold + 0.02)
        elif signal == FeedbackSignal.modified:
            threshold = min(0.95, threshold + 0.005)
        self._profile = profile.model_copy(
            update={
                "evidence_threshold": round(threshold, 4),
                "learned_feedback_count": profile.learned_feedback_count + 1,
                "version": profile.version + 1,
                "updated_at": datetime.now(timezone.utc),
            }
        )

    @staticmethod
    def _score(profile: TwinProfile, option) -> ScenarioScore:
        goal_weights = [goal.priority / 100 for goal in profile.goals if goal.active and goal.domain == option.domain]
        goal_fit = sum(goal_weights) / len(goal_weights) if goal_weights else 0.5
        risk_tolerance = {
            RiskPosture.conservative: 0.25,
            RiskPosture.balanced: 0.55,
            RiskPosture.assertive: 0.8,
        }[profile.risk_posture]
        risk_adjustment = max(0.0, 1 - abs(option.risk - risk_tolerance))
        evidence_gap = abs(option.evidence_quality - profile.evidence_threshold)
        evidence_adjustment = max(0.0, 1 - evidence_gap)
        speed_fit = 1 - abs(option.time_pressure - profile.decision_speed / 100)
        fit = (
            option.expected_value * 0.28
            + goal_fit * 0.24
            + option.reversibility * 0.13
            + speed_fit * 0.1
            + risk_adjustment * 0.13
            + evidence_adjustment * 0.12
        )
        score = min(1.0, max(0.0, fit))
        reasons = [
            f"goal fit {goal_fit:.0%}",
            f"risk fit {risk_adjustment:.0%}",
            f"evidence fit {evidence_adjustment:.0%}",
            f"reversibility {option.reversibility:.0%}",
        ]
        if option.requires_approval:
            reasons.append("human approval required")
        return ScenarioScore(
            option_id=option.id,
            title=option.title,
            score=round(score, 4),
            fit=round(goal_fit, 4),
            risk_adjustment=round(risk_adjustment, 4),
            evidence_adjustment=round(evidence_adjustment, 4),
            reasons=reasons,
        )


digital_twin_service = DigitalTwinService()
