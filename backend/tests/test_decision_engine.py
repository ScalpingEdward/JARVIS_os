import pytest

from app.decision_engine.models import Criterion, DecisionDomain, DecisionRequest, DecisionState, OptionInput
from app.decision_engine.service import decision_engine_service


@pytest.fixture(autouse=True)
def reset_service():
    decision_engine_service.reset()


def test_recommends_best_option_with_human_approval():
    record = decision_engine_service.evaluate(
        DecisionRequest(
            title="Choose implementation strategy",
            domain=DecisionDomain.engineering,
            criteria=[Criterion(name="quality", weight=60), Criterion(name="speed", weight=40)],
            options=[
                OptionInput(name="A", scores={"quality": 90, "speed": 70}, risk=20, evidence_quality=85),
                OptionInput(name="B", scores={"quality": 60, "speed": 95}, risk=35, evidence_quality=75),
            ],
        )
    )
    assert record.state == DecisionState.recommended
    assert record.selected_option == "A"
    assert record.requires_human_approval is True
    assert record.automatic_execution is False


def test_low_confidence_requires_review():
    record = decision_engine_service.evaluate(
        DecisionRequest(
            title="Research choice",
            domain=DecisionDomain.research,
            criteria=[Criterion(name="value", weight=100)],
            options=[
                OptionInput(name="A", scores={"value": 90}, evidence_quality=40),
                OptionInput(name="B", scores={"value": 70}, evidence_quality=80),
            ],
            minimum_confidence=65,
        )
    )
    assert record.state == DecisionState.needs_review


def test_blocker_rejects_top_option_and_cannot_be_approved():
    record = decision_engine_service.evaluate(
        DecisionRequest(
            title="Trading setup",
            domain=DecisionDomain.trading,
            criteria=[Criterion(name="setup", weight=100)],
            options=[
                OptionInput(name="Long", scores={"setup": 95}, evidence_quality=90, blockers=["high impact news"]),
                OptionInput(name="Wait", scores={"setup": 50}, evidence_quality=90),
            ],
        )
    )
    assert record.state == DecisionState.rejected
    with pytest.raises(ValueError):
        decision_engine_service.approve(record.id)
