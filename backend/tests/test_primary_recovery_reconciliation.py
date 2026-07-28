from app.services.primary_recovery_reconciliation import PrimaryRecoveryReconciliationService, RecoveryReceipt
import pytest


def permit(**overrides):
    value = {
        "permit_id": "rp-1", "workspace_id": "ws-1", "status": "consumed",
        "recovery_plan_digest": "plan-digest", "primary_adapter_id": "adapter-a",
        "primary_worker_id": "worker-a", "gateway_id": "gateway-a", "risk_brain_blocked": False,
    }
    value.update(overrides)
    return value


def receipt(**overrides):
    value = dict(
        receipt_id="rcpt-1", permit_id="rp-1", recovery_plan_digest="plan-digest",
        primary_adapter_id="adapter-a", primary_worker_id="worker-a", gateway_id="gateway-a",
        operation="GET", target="health://primary", response_digest="response-digest", success=True,
        side_effects=[],
    )
    value.update(overrides)
    return RecoveryReceipt(**value)


def test_clean_recovery_requires_human_approval_then_attests():
    svc = PrimaryRecoveryReconciliationService()
    rec = svc.reconcile(attestation_id="a1", workspace_id="ws-1", consumed_permit=permit(), receipt=receipt(), source_key="s1")
    assert rec.status == "review-required"
    with pytest.raises(ValueError):
        svc.approve("a1", human_approved=False)
    assert svc.approve("a1", human_approved=True).status == "attested"


def test_identity_mismatch_fails_closed():
    svc = PrimaryRecoveryReconciliationService()
    rec = svc.reconcile(attestation_id="a2", workspace_id="ws-1", consumed_permit=permit(), receipt=receipt(primary_worker_id="worker-x"), source_key="s2")
    assert rec.status == "mismatch"
    assert "primary-handoff-identity-mismatch" in rec.findings


def test_side_effect_fails_closed():
    svc = PrimaryRecoveryReconciliationService()
    rec = svc.reconcile(attestation_id="a3", workspace_id="ws-1", consumed_permit=permit(), receipt=receipt(side_effects=["route-mutation"]), source_key="s3")
    assert rec.status == "mismatch"
    assert not rec.side_effect_safe


def test_risk_brain_block_propagates():
    svc = PrimaryRecoveryReconciliationService()
    rec = svc.reconcile(attestation_id="a4", workspace_id="ws-1", consumed_permit=permit(risk_brain_blocked=True), receipt=receipt(), source_key="s4")
    assert rec.risk_brain_blocked
    assert rec.status == "mismatch"


def test_replay_and_workspace_isolation():
    svc = PrimaryRecoveryReconciliationService()
    svc.reconcile(attestation_id="a5", workspace_id="ws-1", consumed_permit=permit(), receipt=receipt(), source_key="same")
    with pytest.raises(ValueError):
        svc.reconcile(attestation_id="a6", workspace_id="ws-1", consumed_permit=permit(), receipt=receipt(), source_key="same")
    rec = svc.reconcile(attestation_id="a7", workspace_id="ws-2", consumed_permit=permit(), receipt=receipt(), source_key="same")
    assert rec.status == "mismatch"
    assert "workspace-mismatch" in rec.findings


def test_non_read_only_operation_is_rejected():
    svc = PrimaryRecoveryReconciliationService()
    rec = svc.reconcile(attestation_id="a8", workspace_id="ws-1", consumed_permit=permit(), receipt=receipt(operation="POST"), source_key="s8")
    assert rec.status == "mismatch"
    assert "non-read-only-operation" in rec.findings
