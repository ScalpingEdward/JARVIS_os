import pytest

from app.schemas.failover_completion_attestation import FailoverCompletionCreate, StandbyExecutionReceipt
from app.services.failover_completion_attestation import FailoverCompletionAttestationService


def payload(**overrides):
    data = dict(
        workspace_id="ws-a", source_key="src-1", requested_by="tester",
        failover_permit_id="permit-1", failover_permit_digest="permit-digest-123",
        failover_authorization_id="auth-1", failover_authorization_digest="auth-digest-123",
        dispatch_plan_id="plan-1", dispatch_plan_digest="plan-digest-123",
        standby_adapter_id="adapter-b", standby_worker_id="worker-b", gateway_id="gateway-1",
        operation="read-status", target="https://example.invalid/status", permit_consumed=True,
        receipt=StandbyExecutionReceipt(
            status="succeeded", response_digest="response-123", receipt_digest="receipt-123",
            duration_ms=42, response_bytes=512, method="GET", adapter_id="adapter-b",
            worker_id="worker-b", gateway_id="gateway-1", operation="read-status",
            target="https://example.invalid/status",
        ),
    )
    data.update(overrides)
    return FailoverCompletionCreate(**data)


def test_clean_failover_can_be_attested_after_human_approval():
    s = FailoverCompletionAttestationService()
    r = s.create(payload())
    assert r.state.value == "evidence-ready"
    r = s.act("ws-a", r.record_id, "reconcile", "ops", "op-1")
    assert r.state.value == "reconciled"
    r = s.act("ws-a", r.record_id, "submit-review", "ops", "op-2")
    r = s.act("ws-a", r.record_id, "approve", "human", "op-3")
    r = s.act("ws-a", r.record_id, "attest", "human", "op-4")
    assert r.state.value == "attested"


def test_binding_mismatch_fails_closed():
    s = FailoverCompletionAttestationService()
    bad = payload(receipt=payload().receipt.model_copy(update={"worker_id": "wrong-worker"}), source_key="src-2")
    r = s.create(bad)
    assert r.state.value == "mismatch"
    with pytest.raises(ValueError, match="mismatch"):
        s.act("ws-a", r.record_id, "reconcile", "ops", "op-5")


def test_side_effect_detection_blocks_attestation_path():
    s = FailoverCompletionAttestationService()
    bad_receipt = payload().receipt.model_copy(update={"write_side_effect_detected": True})
    r = s.create(payload(source_key="src-3", receipt=bad_receipt))
    assert r.state.value == "mismatch"


def test_risk_brain_hard_block_for_protected_operation():
    s = FailoverCompletionAttestationService()
    p = payload(source_key="src-4", operation="trade-execute", receipt=payload().receipt.model_copy(update={"operation": "trade-execute"}))
    r = s.create(p)
    assert r.state.value == "blocked"
    with pytest.raises(ValueError, match="risk brain hard block"):
        s.act("ws-a", r.record_id, "submit-review", "ops", "op-6")


def test_replay_and_duplicate_source_protection():
    s = FailoverCompletionAttestationService()
    r = s.create(payload(source_key="src-5"))
    s.act("ws-a", r.record_id, "reconcile", "ops", "same-op")
    with pytest.raises(ValueError, match="replay"):
        s.act("ws-a", r.record_id, "submit-review", "ops", "same-op")
    with pytest.raises(ValueError, match="duplicate"):
        s.create(payload(source_key="src-5"))


def test_workspace_isolation():
    s = FailoverCompletionAttestationService()
    r = s.create(payload(source_key="src-6"))
    with pytest.raises(KeyError):
        s.get("ws-b", r.record_id)
