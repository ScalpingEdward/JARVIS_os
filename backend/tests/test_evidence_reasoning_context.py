import pytest

from app.schemas.evidence_reasoning_context import ReasoningContextAction, ReasoningContextCreate
from app.services.evidence_reasoning_context import EvidenceAwareReasoningContextService


def payload(*items):
    evidence = list(items) or [{
        "memory_record_id": "mem-1",
        "provenance_record_id": "prov-1",
        "source_citation": "source://one",
        "claim_key": "market-regime",
        "claim_value": "risk-on",
        "evidence_bundle_digest": "sha256:evidence-1",
        "confidence": 0.95,
        "freshness": 0.95,
        "source_reliability": 0.95,
        "corroboration_count": 2,
        "criticality": 0.5,
    }]
    return ReasoningContextCreate(
        workspace_id="ws-a",
        source_key="reasoning-001",
        requested_by="planner",
        objective="assemble trusted context",
        evidence=evidence,
    )


def action(name, op, reason=None):
    return ReasoningContextAction(
        workspace_id="ws-a", action=name, actor="owner", operation_id=op, reason=reason
    )


def test_status_exposes_safety_boundary():
    status = EvidenceAwareReasoningContextService().status()
    assert status["version"] == "21.124"
    assert status["context_assembly_enabled"] is True
    assert status["automatic_external_actions_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_safe_context_can_be_approved_and_marked_ready():
    service = EvidenceAwareReasoningContextService()
    record = service.create(payload())
    assert record.state.value == "review-required"
    record = service.act(record.record_id, action("approve", "op-1"))
    record = service.act(record.record_id, action("mark-ready", "op-2"))
    assert record.state.value == "ready"
    assert record.citations == ["source://one"]


def test_conflicting_claims_require_resolution():
    first = {
        "memory_record_id": "mem-1", "provenance_record_id": "prov-1", "source_citation": "source://one",
        "claim_key": "market-regime", "claim_value": "risk-on", "evidence_bundle_digest": "sha256:evidence-1",
        "confidence": .95, "freshness": .95, "source_reliability": .95, "criticality": .8,
    }
    second = {
        "memory_record_id": "mem-2", "provenance_record_id": "prov-2", "source_citation": "source://two",
        "claim_key": "market-regime", "claim_value": "risk-off", "evidence_bundle_digest": "sha256:evidence-2",
        "confidence": .90, "freshness": .90, "source_reliability": .90, "criticality": .8,
    }
    service = EvidenceAwareReasoningContextService()
    record = service.create(payload(first, second))
    assert record.state.value == "conflict"
    with pytest.raises(ValueError, match="conflicts must be resolved"):
        service.act(record.record_id, action("approve", "op-a"))
    record = service.act(record.record_id, action("resolve-conflicts", "op-b", "prefer freshest corroborated source"))
    record = service.act(record.record_id, action("approve", "op-c"))
    assert record.state.value == "approved"


def test_low_trust_evidence_is_excluded():
    low = {
        "memory_record_id": "mem-low", "provenance_record_id": "prov-low", "source_citation": "source://low",
        "claim_key": "x", "claim_value": "y", "evidence_bundle_digest": "sha256:low",
        "confidence": .2, "freshness": .2, "source_reliability": .2,
    }
    service = EvidenceAwareReasoningContextService()
    with pytest.raises(ValueError, match="no evidence satisfies"):
        service.create(payload(low))


def test_replay_and_workspace_isolation():
    service = EvidenceAwareReasoningContextService()
    record = service.create(payload())
    service.act(record.record_id, action("approve", "same-op"))
    with pytest.raises(ValueError, match="replay"):
        service.act(record.record_id, action("mark-ready", "same-op"))
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = EvidenceAwareReasoningContextService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
