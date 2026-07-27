import pytest

from app.schemas.external_data_provenance_evidence import ExternalEvidenceAction, ExternalEvidenceCreate
from app.services.external_data_provenance_evidence import ExternalDataProvenanceEvidenceService


def payload(**overrides):
    observation = {
        "response_id": "response-001",
        "connector_id": "github-readonly-adapter",
        "source_uri": "https://api.github.com/repos/ScalpingEdward/JARVIS_os",
        "source_identity": "github:ScalpingEdward/JARVIS_os",
        "source_timestamp": "2026-07-27T06:00:00Z",
        "observed_at": "2026-07-27T06:00:01Z",
        "evidence_hash": "sha256:evidence",
        "payload_digest": "sha256:payload",
        "confidence": 0.95,
        "freshness": 0.95,
        "source_reliability": 0.95,
        "schema_validation_passed": True,
        "sanitization_passed": True,
        "accepted_response": True,
        "corroboration_count": 1,
    }
    observation.update(overrides)
    return ExternalEvidenceCreate(
        workspace_id="ws-a",
        source_key="evidence-source",
        requested_by="orchestrator",
        observations=[observation],
    )


def action(name, op):
    return ExternalEvidenceAction(workspace_id="ws-a", action=name, actor="owner", operation_id=op)


def test_status_exposes_provenance_boundary():
    status = ExternalDataProvenanceEvidenceService().status()
    assert status["version"] == "21.122"
    assert status["provenance_binding_enabled"] is True
    assert status["raw_response_forwarding_enabled"] is False
    assert status["external_write_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_healthy_evidence_can_be_approved_and_activated():
    service = ExternalDataProvenanceEvidenceService()
    record = service.create(payload())
    assert not record.risk_flags
    assert record.evidence_bundle_digest
    record = service.act(record.record_id, action("approve", "op-1"))
    record = service.act(record.record_id, action("activate", "op-2"))
    assert record.state.value == "active"


def test_stale_evidence_blocks_approval():
    service = ExternalDataProvenanceEvidenceService()
    record = service.create(payload(freshness=0.2))
    assert any(flag.startswith("stale-evidence") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act(record.record_id, action("approve", "op-a"))


def test_critical_invalid_evidence_hard_blocks():
    service = ExternalDataProvenanceEvidenceService()
    p = payload(accepted_response=False, schema_validation_passed=False, freshness=0.1, confidence=0.2)
    p.criticality = 0.98
    record = service.create(p)
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_replay_and_workspace_isolation():
    service = ExternalDataProvenanceEvidenceService()
    record = service.create(payload())
    service.act(record.record_id, action("submit-review", "same-op"))
    with pytest.raises(ValueError, match="replay"):
        service.act(record.record_id, action("approve", "same-op"))
    with pytest.raises(KeyError):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_rejected():
    service = ExternalDataProvenanceEvidenceService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
