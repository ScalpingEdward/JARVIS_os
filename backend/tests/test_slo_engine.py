from datetime import datetime, timedelta, timezone

import pytest

from app.slo_engine.models import (
    BudgetAction, IndicatorKind, MeasurementCreate, Mutation, SLOCreate,
    SLOHealth, SLOState,
)
from app.slo_engine.service import SLOService


def _slo(workspace: str = "alpha", owner: str = "owner", **overrides) -> SLOCreate:
    data = dict(
        workspace_id=workspace,
        owner_id=owner,
        slo_key=f"event-bus-{workspace}",
        name="Event bus availability",
        service_key="event-bus",
        operation="publish",
        indicator_kind=IndicatorKind.AVAILABILITY,
        objective_percent=99.0,
        warning_budget_remaining_percent=25.0,
        critical_budget_remaining_percent=0.0,
        fast_burn_threshold=10.0,
        slow_burn_threshold=2.0,
    )
    data.update(overrides)
    return SLOCreate(**data)


def _measurement(slo_id, good: int, total: int, workspace: str = "alpha") -> MeasurementCreate:
    start = datetime.now(timezone.utc) - timedelta(minutes=5)
    return MeasurementCreate(
        workspace_id=workspace,
        requester_id="owner",
        slo_id=slo_id,
        total_events=total,
        good_events=good,
        window_start=start,
        window_end=start + timedelta(minutes=5),
        source_reference="observability/run-1",
    )


def test_slo_lifecycle_healthy_evaluation_and_isolation() -> None:
    service = SLOService()
    slo = service.create_slo(_slo())
    assert slo.state == SLOState.DRAFT
    active = service.set_state(slo.id, "alpha", Mutation(requester_id="owner"), SLOState.ACTIVE)
    assert active is not None and active.state == SLOState.ACTIVE

    measurement, evaluation = service.record_measurement(_measurement(slo.id, 9995, 10000))
    assert measurement.observed_percent == 99.95
    assert evaluation.health == SLOHealth.HEALTHY
    assert evaluation.recommended_action == BudgetAction.NONE
    assert service.get_slo(slo.id, "beta") is None
    assert service.metrics("alpha").healthy_slos == 1


def test_budget_risk_and_exhaustion() -> None:
    service = SLOService()
    slo = service.create_slo(_slo())
    service.set_state(slo.id, "alpha", Mutation(requester_id="owner"), SLOState.ACTIVE)

    _, at_risk = service.record_measurement(_measurement(slo.id, 9920, 10000))
    assert at_risk.health == SLOHealth.AT_RISK
    assert at_risk.requires_review is True

    _, exhausted = service.record_measurement(_measurement(slo.id, 9500, 10000))
    assert exhausted.health == SLOHealth.EXHAUSTED
    assert exhausted.recommended_action in {BudgetAction.FREEZE_PLANNED, BudgetAction.ESCALATION_PLANNED}
    assert service.metrics("alpha").exhausted_slos == 1


def test_zero_error_budget_and_validation() -> None:
    service = SLOService()
    slo = service.create_slo(_slo(objective_percent=100.0))
    service.set_state(slo.id, "alpha", Mutation(requester_id="owner"), SLOState.ACTIVE)
    _, evaluation = service.record_measurement(_measurement(slo.id, 99, 100))
    assert evaluation.health == SLOHealth.EXHAUSTED
    assert evaluation.burn_rate > 1_000_000

    with pytest.raises(ValueError, match="good_events cannot exceed"):
        _measurement(slo.id, 101, 100)
    with pytest.raises(ValueError, match="latency objectives require"):
        _slo(indicator_kind=IndicatorKind.LATENCY)


def test_duplicate_key_ownership_and_safety_guards() -> None:
    service = SLOService()
    slo = service.create_slo(_slo())
    with pytest.raises(ValueError, match="active SLO key"):
        service.create_slo(_slo())
    assert service.set_state(slo.id, "alpha", Mutation(requester_id="other"), SLOState.ACTIVE) is None

    with pytest.raises(ValueError, match="automatic SLO activation"):
        SLOCreate(**{**_slo().model_dump(), "automatic_activation": True})
    with pytest.raises(ValueError, match="never enforce operational changes"):
        SLOCreate(**{**_slo().model_dump(), "automatic_enforcement": True})
    with pytest.raises(ValueError, match="automatic external metric collection"):
        MeasurementCreate(**{**_measurement(slo.id, 100, 100).model_dump(), "collect_external": True})
    with pytest.raises(ValueError, match="external SLO providers"):
        SLOCreate(**{**_slo().model_dump(), "external_provider": True})
