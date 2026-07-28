import pytest
from app.services.reliability_baseline_commit import ReliabilityBaselineCommitService


def closure(**overrides):
    value = {
        "closure_id": "c1",
        "workspace_id": "ws-1",
        "status": "closed",
        "human_approved": True,
        "risk_brain_blocked": False,
        "proposed_baseline": 0.84,
    }
    value.update(overrides)
    return value


def test_human_approved_closure_can_create_and_activate_baseline():
    svc = ReliabilityBaselineCommitService()
    rec = svc.propose(baseline_id="b1", workspace_id="ws-1", subject_id="adapter-a", closure=closure(), operation_id="op1")
    assert rec.status == "review-required"
    assert rec.version == 1
    active = svc.approve("ws-1", "adapter-a", 1, actor="human", operation_id="op2")
    assert active.status == "active"
    assert active.approved_by == "human"


def test_requires_closed_human_approved_incident():
    svc = ReliabilityBaselineCommitService()
    with pytest.raises(ValueError):
        svc.propose(baseline_id="b2", workspace_id="ws-1", subject_id="adapter-a", closure=closure(status="review-required"), operation_id="op3")


def test_risk_brain_block_propagates():
    svc = ReliabilityBaselineCommitService()
    with pytest.raises(ValueError):
        svc.propose(baseline_id="b3", workspace_id="ws-1", subject_id="adapter-a", closure=closure(risk_brain_blocked=True), operation_id="op4")


def test_versioning_and_rollback_are_separately_approved():
    svc = ReliabilityBaselineCommitService()
    svc.propose(baseline_id="b4", workspace_id="ws-1", subject_id="adapter-a", closure=closure(proposed_baseline=0.80), operation_id="op5")
    svc.approve("ws-1", "adapter-a", 1, actor="human", operation_id="op6")
    svc.propose(baseline_id="b5", workspace_id="ws-1", subject_id="adapter-a", closure=closure(closure_id="c2", proposed_baseline=0.88), operation_id="op7")
    svc.approve("ws-1", "adapter-a", 2, actor="human", operation_id="op8")
    rb = svc.propose_rollback("ws-1", "adapter-a", target_version=1, actor="human", operation_id="op9")
    assert rb.status == "rollback-review-required"
    assert rb.baseline_value == 0.80
    active = svc.approve_rollback("ws-1", "adapter-a", rb.version, actor="human-2", operation_id="op10")
    assert active.status == "active"
    assert active.rollback_target_version == 1


def test_operation_replay_is_blocked():
    svc = ReliabilityBaselineCommitService()
    svc.propose(baseline_id="b6", workspace_id="ws-1", subject_id="adapter-a", closure=closure(), operation_id="same")
    with pytest.raises(ValueError):
        svc.propose(baseline_id="b7", workspace_id="ws-1", subject_id="adapter-b", closure=closure(), operation_id="same")


def test_workspace_isolation():
    svc = ReliabilityBaselineCommitService()
    with pytest.raises(ValueError):
        svc.propose(baseline_id="b8", workspace_id="ws-2", subject_id="adapter-a", closure=closure(), operation_id="op11")
