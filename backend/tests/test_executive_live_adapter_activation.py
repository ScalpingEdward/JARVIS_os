from uuid import uuid4

import pytest

from app.executive_live_adapter_activation.models import AdapterRuntimeObservation, ActivationRequest, LiveAdapterActivationCreate, LiveAdapterActivationState
from app.executive_live_adapter_activation.service import executive_live_adapter_activation_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    executive_live_adapter_activation_service.reset()


def payload(**overrides) -> LiveAdapterActivationCreate:
    values = {
        "continuity_state": "continuity-ready",
        "deployment_package_signed": True,
        "artifact_checksum_verified": True,
        "dependency_lock_verified": True,
        "migration_plan_verified": True,
        "rollback_package_verified": True,
        "secret_references_resolved": True,
        "raw_secrets_present": False,
        "adapter_health_verified": True,
        "broker_session_ready": True,
        "market_data_ready": True,
        "executor_transport_ready": True,
        "dry_run_completed": True,
        "dry_run_order_count": 3,
        "dry_run_errors": 0,
        "dry_run_reconciliation_verified": True,
        "human_approval_verified": True,
        "activation_dispatched": True,
        "activation_acknowledged": True,
        "live_session_identity_verified": True,
        "live_positions_reconciled": True,
        "live_pending_orders_reconciled": True,
        "health_probe_registered": True,
        "rollback_probe_registered": True,
    }
    values.update(overrides)
    return LiveAdapterActivationCreate(
        workspace_id="master-brano",
        source_key=str(uuid4()),
        actor_id="master-brano",
        deployment_id=uuid4(),
        adapter_reference="mt5-primary",
        observation=AdapterRuntimeObservation(**values),
    )


def test_production_ready() -> None:
    record = executive_live_adapter_activation_service.assess(payload())
    assert record.state == LiveAdapterActivationState.production_ready
    assert record.production_actions_enabled is True


def test_continuity_dependency() -> None:
    record = executive_live_adapter_activation_service.assess(payload(continuity_state="health-degraded"))
    assert record.state == LiveAdapterActivationState.continuity_required


def test_package_validation() -> None:
    record = executive_live_adapter_activation_service.assess(payload(artifact_checksum_verified=False))
    assert record.state == LiveAdapterActivationState.package_invalid


def test_raw_secrets_blocked() -> None:
    record = executive_live_adapter_activation_service.assess(payload(raw_secrets_present=True))
    assert record.state == LiveAdapterActivationState.secrets_required


def test_adapter_health_required() -> None:
    record = executive_live_adapter_activation_service.assess(payload(adapter_health_verified=False))
    assert record.state == LiveAdapterActivationState.adapter_unhealthy


def test_dry_run_required() -> None:
    record = executive_live_adapter_activation_service.assess(payload(dry_run_errors=1))
    assert record.state == LiveAdapterActivationState.dry_run_required


def test_approval_required() -> None:
    record = executive_live_adapter_activation_service.assess(payload(human_approval_verified=False))
    assert record.state == LiveAdapterActivationState.approval_required


def test_activation_pending() -> None:
    record = executive_live_adapter_activation_service.assess(payload(activation_acknowledged=False))
    assert record.state == LiveAdapterActivationState.activation_pending


def test_reconciliation_required() -> None:
    record = executive_live_adapter_activation_service.assess(payload(live_positions_reconciled=False))
    assert record.state == LiveAdapterActivationState.reconciliation_required


def test_activate_requires_human_approval() -> None:
    record = executive_live_adapter_activation_service.assess(payload(human_approval_verified=False))
    with pytest.raises(ValueError):
        executive_live_adapter_activation_service.activate(ActivationRequest(workspace_id=record.workspace_id, deployment_id=record.deployment_id, actor_id="master-brano", human_approval_verified=False, activation_dispatched=True, activation_acknowledged=True, live_session_identity_verified=True, live_positions_reconciled=True, live_pending_orders_reconciled=True))


def test_risk_brain_block() -> None:
    request = payload()
    request.risk_brain_clear = False
    record = executive_live_adapter_activation_service.assess(request)
    assert record.state == LiveAdapterActivationState.blocked


def test_duplicate_source_key_rejected() -> None:
    request = payload()
    executive_live_adapter_activation_service.assess(request)
    with pytest.raises(ValueError):
        executive_live_adapter_activation_service.assess(request)


def test_workspace_isolation() -> None:
    record = executive_live_adapter_activation_service.assess(payload())
    assert executive_live_adapter_activation_service.get(record.id, "other-workspace") is None
