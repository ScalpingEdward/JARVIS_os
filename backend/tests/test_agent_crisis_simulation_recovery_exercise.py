import pytest

from app.schemas.agent_crisis_simulation_recovery_exercise import CrisisExerciseCreate
from app.services.agent_crisis_simulation_recovery_exercise import AgentCrisisSimulationRecoveryExerciseService


def payload(**overrides):
    observation = {
        "agent_id": "phoenix-agent",
        "agent_version": "21.105",
        "exercise_id": "exercise-001",
        "scenario_coverage": 0.98,
        "severity_realism": 0.95,
        "incident_command_readiness": 0.98,
        "decision_timing_quality": 0.95,
        "communication_readiness": 0.98,
        "recovery_sequence_quality": 0.98,
        "rto_attainment": 0.98,
        "rpo_attainment": 0.98,
        "dependency_coordination": 0.95,
        "runbook_effectiveness": 0.98,
        "evidence_capture": 0.98,
        "lessons_learned_quality": 0.95,
        "confidence": 1.0,
        "freshness": 1.0,
        "business_criticality": 0.70,
    }
    observation.update(overrides)
    return CrisisExerciseCreate(
        workspace_id="ws-a",
        source_key="exercise-source",
        requested_by="operator",
        observations=[observation],
    )


def test_status_disables_execution():
    status = AgentCrisisSimulationRecoveryExerciseService().status()
    assert status["version"] == "21.105"
    assert status["scenario_execution_enabled"] is False
    assert status["fault_injection_enabled"] is False
    assert status["automatic_failover_enabled"] is False
    assert status["automatic_recovery_enabled"] is False
    assert status["agent_execution_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_healthy_exercise_can_be_approved():
    service = AgentCrisisSimulationRecoveryExerciseService()
    record = service.create(payload())
    assert not record.risk_flags
    record = service.act("ws-a", record.record_id, "assess", "reviewer", "op-1")
    record = service.act("ws-a", record.record_id, "submit-review", "reviewer", "op-2")
    record = service.act("ws-a", record.record_id, "approve", "owner", "op-3")
    assert record.approved_by == "owner"


def test_command_failure_blocks_approval():
    service = AgentCrisisSimulationRecoveryExerciseService()
    record = service.create(payload(incident_command_readiness=0.40, failed_command_decisions=1))
    assert any(flag.startswith("command-alert") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "owner", "op-a")


def test_critical_recovery_failure_hard_blocks():
    service = AgentCrisisSimulationRecoveryExerciseService()
    record = service.create(payload(
        business_criticality=0.98,
        recovery_sequence_quality=0.30,
        rto_attainment=0.30,
        rpo_attainment=0.30,
        missed_recovery_objectives=2,
    ))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_operation_replay_rejected():
    service = AgentCrisisSimulationRecoveryExerciseService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "reviewer", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "submit-review", "reviewer", "same-op")


def test_workspace_isolation():
    service = AgentCrisisSimulationRecoveryExerciseService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = AgentCrisisSimulationRecoveryExerciseService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
