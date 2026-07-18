import pytest

from app.executive_resilience.models import ContinuityState, ContinuityUpdate, CriticalService, CrisisRole, ResiliencePlanCreate, ResilienceScenario
from app.executive_resilience.service import ExecutiveResilienceService


def payload(workspace_id: str = "ws-1") -> ResiliencePlanCreate:
    return ResiliencePlanCreate(
        workspace_id=workspace_id,
        name="Enterprise Continuity",
        executive_owner_id="ceo",
        services=[
            CriticalService(service_id="data", name="Data Platform", owner_id="cto", criticality="critical", recovery_time_objective_minutes=60, recovery_point_objective_minutes=15, maximum_tolerable_downtime_minutes=240, tested=True),
            CriticalService(service_id="trading", name="Trading Runtime", owner_id="coo", criticality="critical", recovery_time_objective_minutes=30, recovery_point_objective_minutes=5, maximum_tolerable_downtime_minutes=120, dependencies=["data"]),
            CriticalService(service_id="reporting", name="Executive Reporting", owner_id="cfo", recovery_time_objective_minutes=180, recovery_point_objective_minutes=60, maximum_tolerable_downtime_minutes=480, dependencies=["data"]),
        ],
        scenarios=[ResilienceScenario(scenario_id="region-loss", name="Region loss", probability=0.2, impact=0.9, affected_service_ids=["data", "trading"], mitigation_strength=0.5)],
        crisis_roles=[CrisisRole(role_id="commander", name="Crisis Commander", owner_id="coo", backup_owner_id="cto")],
    )


def test_assessment_detects_dependency_concentration_and_untested_services() -> None:
    service = ExecutiveResilienceService()
    plan = service.create(payload())
    assessed = service.assess(plan.id, "ws-1", "ceo")
    assert assessed.assessment is not None
    assert "data" in assessed.assessment.single_points_of_failure
    assert "trading" in assessed.assessment.critical_services_at_risk
    assert assessed.assessment.resilience_score < 100


def test_continuity_update_invalidates_assessment() -> None:
    service = ExecutiveResilienceService()
    plan = service.create(payload())
    service.assess(plan.id, "ws-1", "ceo")
    updated = service.update_continuity(plan.id, "ws-1", ContinuityUpdate(service_id="trading", state=ContinuityState.disrupted, actor_id="coo"))
    assert updated.assessment is None
    reassessed = service.assess(plan.id, "ws-1", "ceo")
    assert "trading" in reassessed.assessment.critical_services_at_risk


def test_workspace_isolation() -> None:
    service = ExecutiveResilienceService()
    plan = service.create(payload("alpha"))
    assert service.get(plan.id, "beta") is None
    assert service.list_plans("beta") == []


def test_duplicate_names_are_rejected_per_workspace() -> None:
    service = ExecutiveResilienceService()
    service.create(payload())
    with pytest.raises(ValueError, match="already exists"):
        service.create(payload())


def test_dependency_cycles_are_rejected() -> None:
    service = ExecutiveResilienceService()
    cycle = ResiliencePlanCreate(
        workspace_id="ws",
        name="Cycle",
        executive_owner_id="ceo",
        services=[
            CriticalService(service_id="a", name="A", owner_id="a", recovery_time_objective_minutes=1, recovery_point_objective_minutes=0, maximum_tolerable_downtime_minutes=2, dependencies=["b"]),
            CriticalService(service_id="b", name="B", owner_id="b", recovery_time_objective_minutes=1, recovery_point_objective_minutes=0, maximum_tolerable_downtime_minutes=2, dependencies=["a"]),
        ],
    )
    with pytest.raises(ValueError, match="cycle"):
        service.create(cycle)


def test_autonomous_actions_are_disabled() -> None:
    service = ExecutiveResilienceService()
    assert service.status("ws").autonomous_actions_enabled is False
