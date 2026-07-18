import pytest

from app.continuous_learning.models import (
    ExperienceCreate,
    ExperienceType,
    ImprovementCreate,
    MetricValue,
    OutcomeCreate,
    OutcomeStatus,
    RecommendationReview,
    RecommendationState,
)
from app.continuous_learning.service import ContinuousLearningService


@pytest.fixture
def service() -> ContinuousLearningService:
    return ContinuousLearningService()


def _experience(service: ContinuousLearningService, workspace: str = "alpha", key: str = "mission.one"):
    return service.create_experience(
        ExperienceCreate(
            workspace_id=workspace,
            owner_id="owner-1",
            key=key,
            experience_type=ExperienceType.MISSION,
            title="Mission outcome",
            expected_metrics=[MetricValue(key="quality", value=90), MetricValue(key="duration", value=60)],
            tags=["jarvis"],
        )
    )


def _outcome(
    service: ContinuousLearningService,
    experience_id,
    status: OutcomeStatus,
    quality: float,
    cause: str | None = None,
    workspace: str = "alpha",
):
    return service.create_outcome(
        OutcomeCreate(
            workspace_id=workspace,
            actor_id="reviewer-1",
            experience_id=experience_id,
            status=status,
            actual_metrics=[MetricValue(key="quality", value=quality), MetricValue(key="duration", value=75)],
            root_causes=[cause] if cause else [],
            lessons=["Use stronger validation"],
        )
    )


def test_outcome_calculates_expected_actual_deltas(service: ContinuousLearningService) -> None:
    experience = _experience(service)
    outcome = _outcome(service, experience.id, OutcomeStatus.SUCCESS, 95)
    quality = next(item for item in outcome.metric_deltas if item.key == "quality")
    assert quality.absolute_delta == 5
    assert quality.percentage_delta == pytest.approx(5.5556)


def test_repeated_failures_generate_patterns_and_recommendations(service: ContinuousLearningService) -> None:
    first = _experience(service, key="mission.one")
    second = _experience(service, key="mission.two")
    _outcome(service, first.id, OutcomeStatus.FAILURE, 60, "missing approval")
    _outcome(service, second.id, OutcomeStatus.FAILURE, 55, "missing approval")

    patterns = service.list_patterns("alpha")
    recommendations = service.list_recommendations("alpha")
    assert any(item.key == "status.failure" for item in patterns)
    assert any(item.key == "cause.missing-approval" for item in patterns)
    assert recommendations
    assert all(not item.automatic_application_enabled for item in recommendations)


def test_recommendation_requires_review_before_improvement(service: ContinuousLearningService) -> None:
    first = _experience(service, key="mission.one")
    second = _experience(service, key="mission.two")
    _outcome(service, first.id, OutcomeStatus.FAILURE, 60, "capacity shortage")
    _outcome(service, second.id, OutcomeStatus.FAILURE, 58, "capacity shortage")
    recommendation = service.list_recommendations("alpha")[0]

    with pytest.raises(ValueError, match="approved"):
        service.create_improvement(
            ImprovementCreate(
                workspace_id="alpha",
                owner_id="owner-2",
                recommendation_id=recommendation.id,
            )
        )

    reviewed = service.review_recommendation(
        recommendation.id,
        RecommendationReview(workspace_id="alpha", reviewer_id="reviewer-2", approve=True),
    )
    assert reviewed.state == RecommendationState.APPROVED
    improvement = service.create_improvement(
        ImprovementCreate(
            workspace_id="alpha",
            owner_id="owner-2",
            recommendation_id=recommendation.id,
            verification_metric="failure-rate",
            baseline_value=0.4,
        )
    )
    assert improvement.recommendation_id == recommendation.id


def test_drift_detection_compares_older_and_recent_samples(service: ContinuousLearningService) -> None:
    values = [100, 102, 70, 68]
    for index, value in enumerate(values):
        experience = service.create_experience(
            ExperienceCreate(
                workspace_id="alpha",
                owner_id="owner",
                key=f"sample.{index}",
                experience_type=ExperienceType.AGENT,
                title="Agent sample",
                expected_metrics=[MetricValue(key="throughput", value=100)],
            )
        )
        service.create_outcome(
            OutcomeCreate(
                workspace_id="alpha",
                actor_id="reviewer",
                experience_id=experience.id,
                status=OutcomeStatus.PARTIAL,
                actual_metrics=[MetricValue(key="throughput", value=value)],
            )
        )
    drift = service.drift("alpha")
    record = next(item for item in drift if item.metric_key == "throughput")
    assert record.recent_mean < record.baseline_mean
    assert record.severity in {"warning", "critical"}


def test_workspace_isolation(service: ContinuousLearningService) -> None:
    experience = _experience(service, workspace="alpha")
    assert service.get_experience("beta", experience.id) is None
    with pytest.raises(ValueError, match="not found"):
        _outcome(service, experience.id, OutcomeStatus.SUCCESS, 95, workspace="beta")
    assert service.list_experiences("beta") == []


def test_duplicate_experience_keys_are_rejected(service: ContinuousLearningService) -> None:
    _experience(service)
    with pytest.raises(ValueError, match="already exists"):
        _experience(service)


def test_automatic_external_action_is_rejected() -> None:
    with pytest.raises(ValueError, match="automatic external actions"):
        ExperienceCreate(
            workspace_id="alpha",
            owner_id="owner",
            key="unsafe",
            experience_type=ExperienceType.PLAYBOOK,
            title="Unsafe",
            automatic_external_action=True,
        )
