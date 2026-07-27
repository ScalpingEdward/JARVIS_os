import pytest

from app.schemas.change_proposal_safe_execution import ChangeProposalCreate
from app.services.change_proposal_safe_execution import ChangeProposalSafeExecutionService


def payload(**overrides):
    base = {
        "workspace_id": "ws-a",
        "source_key": "change-source",
        "requested_by": "operator",
        "candidate_id": "candidate-111",
        "target_system": "phoenix-agent",
        "rationale": "validated optimization candidate",
        "expected_gain": 0.12,
        "validation_confidence": 0.95,
        "blast_radius": 0.20,
        "rollback_readiness": 0.95,
        "observability_readiness": 0.95,
        "dependency_readiness": 0.95,
        "execution_window_ready": True,
        "preconditions": ["health-green", "dependencies-green"],
        "postconditions": ["slo-green", "candidate-kpi-met"],
        "rollback_criteria": ["error-rate-breach", "latency-regression"],
        "steps": [{"step_id": "s1", "action": "apply-candidate", "target": "phoenix-agent", "parameters": {"mode": "candidate"}, "reversible": True}],
    }
    base.update(overrides)
    return ChangeProposalCreate(**base)


def test_status_disables_execution():
    status = ChangeProposalSafeExecutionService().status()
    assert status["version"] == "21.112"
    assert status["execution_enabled"] is False
    assert status["configuration_mutation_enabled"] is False
    assert status["deployment_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_complete_contract_can_be_approved_and_authorized():
    service = ChangeProposalSafeExecutionService()
    record = service.create(payload())
    assert record.assessment.execution_contract_complete is True
    assert not record.assessment.risk_flags
    record = service.act("ws-a", record.record_id, "validate", "reviewer", "op-1")
    record = service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-2")
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-3")
    record = service.act("ws-a", record.record_id, "authorize-execution-contract", "change-manager", "op-4")
    assert record.state.value == "execution-ready"
    assert record.approved_by == "owner"
    assert record.execution_authorized_by == "change-manager"


def test_missing_window_blocks_validation():
    service = ChangeProposalSafeExecutionService()
    record = service.create(payload(execution_window_ready=False))
    assert "execution-window-not-ready" in record.assessment.risk_flags
    with pytest.raises(ValueError, match="incomplete execution contract"):
        service.act("ws-a", record.record_id, "validate", "reviewer", "op-a")


def test_high_blast_radius_can_hard_block():
    service = ChangeProposalSafeExecutionService()
    record = service.create(payload(blast_radius=0.95, rollback_readiness=0.60))
    assert "risk-brain-hard-block" in record.assessment.risk_flags
    assert record.state.value == "blocked"


def test_replay_and_workspace_isolation():
    service = ChangeProposalSafeExecutionService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "validate", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = ChangeProposalSafeExecutionService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
