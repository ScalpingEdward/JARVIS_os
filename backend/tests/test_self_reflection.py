import pytest

from app.self_reflection.models import ExperimentCreate, ExperimentMode, Outcome, ReviewCreate, ReviewDomain
from app.self_reflection.service import reflection_service


def setup_function() -> None:
    reflection_service.reset()


def test_recurring_failures_generate_proposal_and_require_approval() -> None:
    payload = ReviewCreate(
        domain=ReviewDomain.mission,
        subject_id="mission-1",
        objective="Ship feature",
        outcome=Outcome.partial,
        score=65,
        failures=["missing test coverage"],
        evidence=["ci-log-1"],
    )
    reflection_service.add_review(payload)
    reflection_service.add_review(payload.model_copy(update={"subject_id": "mission-2"}))

    proposals = reflection_service.propose_improvements()
    assert len(proposals) == 1
    assert proposals[0].requires_human_approval is True

    with pytest.raises(ValueError, match="Human approval"):
        reflection_service.create_experiment(
            ExperimentCreate(
                proposal_id=proposals[0].id,
                mode=ExperimentMode.shadow,
                hypothesis="Mandatory test checklist reduces failures",
            )
        )

    reflection_service.approve_proposal(proposals[0].id)
    experiment = reflection_service.create_experiment(
        ExperimentCreate(
            proposal_id=proposals[0].id,
            mode=ExperimentMode.shadow,
            hypothesis="Mandatory test checklist reduces failures",
        )
    )
    assert experiment.status == "planned"


def test_reflection_status_disables_self_modification_and_trading_execution() -> None:
    status = reflection_service.status()
    assert status.automatic_self_modification is False
    assert status.automatic_order_execution is False
    assert status.automatic_merge is False
