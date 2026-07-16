from app.decision_memory.models import DecisionDomain, DecisionOutcome, DecisionRecordCreate
from app.decision_memory.service import decision_memory_service


def setup_function() -> None:
    decision_memory_service.reset()


def test_memory_is_advisory_and_owned_by_master_brano() -> None:
    status = decision_memory_service.status()
    assert status.owner_name == "MASTER Brano"
    assert status.automatic_execution is False
    assert status.automatic_order_execution is False


def test_learning_requires_explicit_consent() -> None:
    decision_memory_service.add(
        DecisionRecordCreate(
            title="Unapproved learning example",
            domain=DecisionDomain.business,
            recommendation="Wait for more evidence",
            selected_action="Proceed immediately",
            predicted_confidence=0.8,
            outcome=DecisionOutcome.unsuccessful,
            outcome_score=0.2,
            learning_consent=False,
        )
    )
    report = decision_memory_service.calibration()
    assert report.sample_size == 0
    assert report.status == "insufficient_data"


def test_calibration_detects_overconfidence() -> None:
    for index in range(2):
        decision_memory_service.add(
            DecisionRecordCreate(
                title=f"Trading decision {index + 1}",
                domain=DecisionDomain.trading,
                recommendation="Take the setup",
                selected_action="Take the setup",
                predicted_confidence=0.9,
                outcome=DecisionOutcome.unsuccessful,
                outcome_score=0.3,
                learning_consent=True,
            )
        )
    report = decision_memory_service.calibration(DecisionDomain.trading)
    assert report.sample_size == 2
    assert report.status == "overconfident"
    assert report.calibration_gap > 0


def test_patterns_detect_reliable_outcomes() -> None:
    for index in range(3):
        decision_memory_service.add(
            DecisionRecordCreate(
                title=f"Research decision {index + 1}",
                domain=DecisionDomain.research,
                recommendation="Verify with primary sources",
                selected_action="Verify with primary sources",
                predicted_confidence=0.8,
                outcome=DecisionOutcome.successful,
                outcome_score=0.9,
                evidence_tags=["primary-source"],
                learning_consent=True,
            )
        )
    patterns = decision_memory_service.patterns(DecisionDomain.research)
    assert any(pattern.title == "Reliable decision pattern" for pattern in patterns)
