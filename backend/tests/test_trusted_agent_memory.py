import pytest

from app.schemas.trusted_agent_memory import TrustedMemoryAction, TrustedMemoryCreate, TrustedMemoryRetrieve
from app.services.trusted_agent_memory import TrustedAgentMemoryService


def payload(**overrides):
    data = {
        "workspace_id": "ws-a",
        "source_key": "memory-001",
        "requested_by": "planner",
        "agent_id": "phoenix-agent",
        "provenance_record_id": "prov-001",
        "evidence_bundle_digest": "sha256:abcdef1234567890",
        "source_uri": "https://api.example.test/resource/1",
        "citation_label": "External source 1",
        "content": "Verified evidence for downstream reasoning.",
        "topics": ["operations", "resilience"],
        "data_domains": ["source-code"],
        "memory_scope": "project",
        "provenance_approved": True,
        "provenance_state": "active",
        "confidence": 0.95,
        "source_reliability": 0.95,
        "freshness": 0.95,
        "ttl_seconds": 3600,
        "criticality": 0.5,
    }
    data.update(overrides)
    return TrustedMemoryCreate(**data)


def action(name, op):
    return TrustedMemoryAction(workspace_id="ws-a", action=name, actor="owner", operation_id=op)


def test_status_exposes_safe_memory_boundary():
    status = TrustedAgentMemoryService().status()
    assert status["version"] == "21.123"
    assert status["trusted_context_ingestion_enabled"] is True
    assert status["raw_external_response_ingestion_enabled"] is False
    assert status["network_fetch_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_approved_evidence_can_be_activated_and_retrieved_with_citation():
    service = TrustedAgentMemoryService()
    record = service.create(payload())
    assert record.state.value == "review-required"
    record = service.act(record.record_id, action("approve", "op-1"))
    record = service.act(record.record_id, action("activate", "op-2"))
    hits = service.retrieve(TrustedMemoryRetrieve(workspace_id="ws-a", agent_id="phoenix-agent", topics=["operations"]))
    assert len(hits) == 1
    assert hits[0].source_uri == "https://api.example.test/resource/1"
    assert hits[0].evidence_bundle_digest.startswith("sha256:")


def test_low_confidence_memory_blocks_approval():
    service = TrustedAgentMemoryService()
    record = service.create(payload(confidence=0.3))
    assert "low-confidence" in record.risk_flags
    with pytest.raises(ValueError, match="findings block approval"):
        service.act(record.record_id, action("approve", "op-1"))


def test_critical_invalid_evidence_hard_blocks():
    service = TrustedAgentMemoryService()
    record = service.create(payload(evidence_bundle_digest="invalid-digest", criticality=0.98))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_unapproved_provenance_is_rejected_at_contract_boundary():
    with pytest.raises(ValueError, match="approved active provenance required"):
        payload(provenance_approved=False)


def test_replay_workspace_isolation_and_duplicate_source():
    service = TrustedAgentMemoryService()
    record = service.create(payload())
    service.act(record.record_id, action("approve", "same-op"))
    with pytest.raises(ValueError, match="replay"):
        service.act(record.record_id, action("activate", "same-op"))
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
