from app.executive_mt5_end_to_end_runtime_validation.models import ComponentHealth, PipelineAssessmentCreate, PipelineExecuteRequest, PipelineState
from app.executive_mt5_end_to_end_runtime_validation.service import EndToEndRuntimeValidationService


def components(**health):
    defaults = {"mt5": True, "market-data": True, "signal-provider": True, "event-bus": True, "database": True}
    defaults.update(health)
    return [ComponentHealth(name=name, healthy=value, heartbeat_age_seconds=1, timeout_seconds=30) for name, value in defaults.items()]


def payload(**updates):
    base = dict(
        workspace_id="ws-a",
        source_key="source-1",
        actor_id="tester",
        strategy_runtime_active=True,
        dependencies_complete=True,
        components=components(),
        account_risk_approved=True,
        prop_rules_approved=True,
        human_approved=True,
        activation_dispatched=True,
        activation_acknowledged=True,
        runtime_reconciled=True,
    )
    base.update(updates)
    return PipelineAssessmentCreate(**base)


def test_requires_v18_94_runtime():
    service = EndToEndRuntimeValidationService()
    assert service.create(payload(strategy_runtime_active=False)).state == PipelineState.RUNTIME_REQUIRED


def test_missing_component_fails_closed():
    service = EndToEndRuntimeValidationService()
    assert service.create(payload(components=components()[:-1])).state == PipelineState.DEPENDENCY_MISSING


def test_stale_heartbeat_blocks():
    service = EndToEndRuntimeValidationService()
    items = components()
    items[0] = ComponentHealth(name="mt5", healthy=True, heartbeat_age_seconds=31, timeout_seconds=30)
    assert service.create(payload(components=items)).state == PipelineState.HEARTBEAT_STALE


def test_component_health_states():
    mapping = {
        "mt5": PipelineState.MT5_UNHEALTHY,
        "market-data": PipelineState.MARKET_DATA_UNHEALTHY,
        "signal-provider": PipelineState.SIGNAL_PROVIDER_UNHEALTHY,
        "event-bus": PipelineState.EVENT_BUS_UNHEALTHY,
        "database": PipelineState.DATABASE_UNHEALTHY,
    }
    for name, expected in mapping.items():
        service = EndToEndRuntimeValidationService()
        assert service.create(payload(source_key=name, components=components(**{name: False}))).state == expected


def test_risk_brain_hard_block():
    service = EndToEndRuntimeValidationService()
    assert service.create(payload(risk_brain_blocked=True)).state == PipelineState.BLOCKED


def test_requires_risk_and_human_approval():
    service = EndToEndRuntimeValidationService()
    assert service.create(payload(account_risk_approved=False)).state == PipelineState.RISK_REJECTED
    service = EndToEndRuntimeValidationService()
    assert service.create(payload(human_approved=False)).state == PipelineState.APPROVAL_REQUIRED


def test_activation_and_reconciliation_flow():
    service = EndToEndRuntimeValidationService()
    record = service.create(payload(activation_dispatched=False, activation_acknowledged=False, runtime_reconciled=False))
    assert record.state == PipelineState.ACTIVATION_PENDING
    record = service.execute(record.id, "ws-a", PipelineExecuteRequest(actor_id="approver", activation_dispatched=True, activation_acknowledged=True))
    assert record.state == PipelineState.RECONCILIATION_REQUIRED
    record = service.execute(record.id, "ws-a", PipelineExecuteRequest(actor_id="approver", runtime_reconciled=True))
    assert record.state == PipelineState.PIPELINE_ACTIVE


def test_recovery_and_pause_states():
    service = EndToEndRuntimeValidationService()
    assert service.create(payload(components=components(mt5=False), recovery_plan_defined=True)).state == PipelineState.RECOVERY_REQUIRED
    service = EndToEndRuntimeValidationService()
    assert service.create(payload(pause_requested=True)).state == PipelineState.PAUSED


def test_duplicate_and_workspace_isolation():
    service = EndToEndRuntimeValidationService()
    record = service.create(payload())
    assert service.get(record.id, "ws-b") is None
    try:
        service.create(payload())
        assert False, "duplicate should fail"
    except ValueError:
        assert True
