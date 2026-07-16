from app.digital_twin.models import (
    FeedbackSignal,
    RiskPosture,
    ScenarioOption,
    ScenarioRequest,
    TwinDomain,
    TwinFeedbackCreate,
    TwinGoal,
    TwinProfileCreate,
)
from app.digital_twin.service import digital_twin_service


def setup_function() -> None:
    digital_twin_service.reset()


def test_profile_defaults_to_master_brano_and_never_executes() -> None:
    profile = digital_twin_service.configure(TwinProfileCreate())
    assert profile.owner_name == "MASTER Brano"
    assert profile.automatic_execution is False
    assert digital_twin_service.status().automatic_order_execution is False


def test_scenario_recommendation_is_explainable_and_human_gated() -> None:
    digital_twin_service.configure(
        TwinProfileCreate(
            risk_posture=RiskPosture.balanced,
            goals=[TwinGoal(domain=TwinDomain.trading, title="Protect funded capital", target="Low drawdown", priority=95)],
        )
    )
    safer = ScenarioOption(
        title="Wait for confirmation",
        description="Wait for structure confirmation before entry",
        domain=TwinDomain.trading,
        expected_value=0.75,
        risk=0.35,
        reversibility=0.9,
        evidence_quality=0.85,
        time_pressure=0.35,
    )
    aggressive = ScenarioOption(
        title="Enter immediately",
        description="Enter before confirmation",
        domain=TwinDomain.trading,
        expected_value=0.65,
        risk=0.9,
        reversibility=0.2,
        evidence_quality=0.45,
        time_pressure=0.9,
    )
    result = digital_twin_service.evaluate(
        ScenarioRequest(question="How should the setup be handled?", options=[safer, aggressive])
    )
    assert result.recommended_option_id == safer.id
    assert result.requires_human_approval is True
    assert result.automatic_execution is False
    assert result.scores[0].reasons


def test_learning_requires_explicit_consent() -> None:
    profile = digital_twin_service.configure(TwinProfileCreate(evidence_threshold=0.72))
    options = [
        ScenarioOption(title="A", description="First option", domain=TwinDomain.business),
        ScenarioOption(title="B", description="Second option", domain=TwinDomain.business),
    ]
    recommendation = digital_twin_service.evaluate(ScenarioRequest(question="Choose option", options=options))
    no_consent = digital_twin_service.add_feedback(
        TwinFeedbackCreate(
            recommendation_id=recommendation.id,
            signal=FeedbackSignal.accepted,
            selected_option_id=recommendation.recommended_option_id,
            allow_learning=False,
        )
    )
    assert no_consent.applied_to_profile is False
    assert digital_twin_service.profile().version == profile.version

    consented = digital_twin_service.add_feedback(
        TwinFeedbackCreate(
            recommendation_id=recommendation.id,
            signal=FeedbackSignal.rejected,
            allow_learning=True,
        )
    )
    assert consented.applied_to_profile is True
    assert digital_twin_service.profile().version == profile.version + 1
    assert digital_twin_service.profile().learned_feedback_count == 1
