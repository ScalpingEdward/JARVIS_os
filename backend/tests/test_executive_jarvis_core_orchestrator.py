from app.executive_jarvis_core_orchestrator.models import JarvisCoreCreate, JarvisCoreExecuteRequest, JarvisCoreState, ModuleCommand
from app.executive_jarvis_core_orchestrator.service import JarvisCoreOrchestratorService


def payload(**overrides):
    data = dict(
        workspace_id="alpha",
        source_key="objective-1",
        actor_id="master-brano",
        objective="Coordinate the approved trading decision pipeline.",
        market_permission_v19_08=True,
        shadow_validation_v19_09=True,
        journal_validation_v19_10=True,
        optimizer_approval_v19_11=True,
        governor_clearance_v19_12=True,
        commands=[ModuleCommand(module="portfolio-governor", action="prepare-controlled-resume")],
    )
    data.update(overrides)
    return JarvisCoreCreate(**data)


def test_requires_human_approval_for_non_protective_plan():
    service = JarvisCoreOrchestratorService()
    record = service.create(payload())
    assert record.state == JarvisCoreState.APPROVAL_REQUIRED


def test_approved_plan_can_execute_and_complete():
    service = JarvisCoreOrchestratorService()
    record = service.create(payload(human_approved=True))
    assert record.state == JarvisCoreState.READY
    record = service.execute(record.id, "alpha", JarvisCoreExecuteRequest(actor_id="master-brano", action="execute", human_approved=True))
    assert record.state == JarvisCoreState.EXECUTING
    assert all(step.status == "dispatched" for step in record.plan)
    record = service.execute(record.id, "alpha", JarvisCoreExecuteRequest(actor_id="master-brano", action="complete"))
    assert record.state == JarvisCoreState.COMPLETED


def test_missing_upstream_evidence_fails_closed():
    service = JarvisCoreOrchestratorService()
    record = service.create(payload(governor_clearance_v19_12=False))
    assert record.state == JarvisCoreState.EVIDENCE_REQUIRED
    assert "v19.12" in record.blocked_modules


def test_risk_brain_block_cannot_be_overridden():
    service = JarvisCoreOrchestratorService()
    record = service.create(payload(upstream_risk_brain_blocked=True, human_approved=True))
    assert record.state == JarvisCoreState.BLOCKED


def test_unsafe_risk_expansion_command_is_blocked():
    service = JarvisCoreOrchestratorService()
    record = service.create(payload(commands=[ModuleCommand(module="risk", action="increase-risk")]))
    assert record.state == JarvisCoreState.BLOCKED


def test_duplicate_source_key_and_workspace_isolation():
    service = JarvisCoreOrchestratorService()
    first = service.create(payload())
    try:
        service.create(payload())
        assert False, "expected duplicate rejection"
    except ValueError:
        pass
    assert service.get(first.id, "other") is None
