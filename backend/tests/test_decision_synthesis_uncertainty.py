import pytest

from app.schemas.decision_synthesis_uncertainty import DecisionSynthesisCreate
from app.services.decision_synthesis_uncertainty import DecisionSynthesisUncertaintyService


def payload(**overrides):
    data = {
        "workspace_id": "ws-a",
        "source_key": "decision-001",
        "requested_by": "planner",
        "reasoning_record_id": "reasoning-001",
        "reasoning_packet_digest": "sha256:reasoning-packet",
        "objective": "choose deployment observation strategy",
        "preferred_alternative_id": "a1",
        "alternatives": [
            {
                "alternative_id": "a1",
                "description": "continue read-only observation",
                "expected_utility": 0.90,
                "confidence": 0.92,
                "downside_risk": 0.10,
                "reversibility": 0.98,
                "evidence_refs": ["mem-1", "mem-2"],
            },
            {
                "alternative_id": "a2",
                "description": "pause and collect more evidence",
                "expected_utility": 0.55,
                "confidence": 0.90,
                "downside_risk": 0.05,
                "reversibility": 1.0,
                "evidence_refs": ["mem-2"],
            },
        ],
        "assumptions": ["current evidence remains fresh"],
        "unresolved_questions": [],
        "aggregate_evidence_confidence": 0.95,
        "aggregate_freshness": 0.95,
        "context_conflict_resolved": True,
        "criticality": 0.60,
    }
    data.update(overrides)
    return DecisionSynthesisCreate(**data)


def test_status_keeps_execution_disabled():
    status = DecisionSynthesisUncertaintyService().status()
    assert status["version"] == "21.125"
    assert status["decision_synthesis_enabled"] is True
    assert status["execution_proposal_generation_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_safe_decision_can_be_approved_and_marked_ready():
    service = DecisionSynthesisUncertaintyService()
    record = service.create(payload())
    assert record.state.value == "review-required"
    assert not record.risk_flags
    record = service.act("ws-a", record.record_id, "approve", "human-owner", "op-1")
    record = service.act("ws-a", record.record_id, "mark-ready", "human-owner", "op-2")
    assert record.state.value == "ready"
    assert record.approved_by == "human-owner"


def test_low_confidence_blocks_approval():
    service = DecisionSynthesisUncertaintyService()
    p = payload()
    p.alternatives[0].confidence = 0.40
    record = service.create(p)
    assert "decision-confidence-below-threshold" in record.risk_flags
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "owner", "op-low")


def test_unresolved_reasoning_conflict_is_not_ready():
    service = DecisionSynthesisUncertaintyService()
    record = service.create(payload(context_conflict_resolved=False))
    assert record.state.value == "conflict"
    assert "reasoning-conflict-unresolved" in record.risk_flags


def test_critical_uncertainty_hard_blocks():
    service = DecisionSynthesisUncertaintyService()
    p = payload(criticality=0.98, aggregate_evidence_confidence=0.20, aggregate_freshness=0.20)
    p.alternatives[0].confidence = 0.20
    p.alternatives[0].downside_risk = 0.95
    record = service.create(p)
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_replay_and_workspace_isolation():
    service = DecisionSynthesisUncertaintyService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "reject", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-a", record.record_id, "archive", "owner", "same-op")
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = DecisionSynthesisUncertaintyService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
