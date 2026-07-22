import pytest

from backend.app.modules.configuration_trust_hardening.models import (
    HardeningControl,
    RiskDecision,
    TrustActionRequest,
    TrustAssessmentCreate,
    TrustEdge,
    TrustNode,
    TrustState,
)
from backend.app.modules.configuration_trust_hardening.service import (
    ConfigurationTrustHardeningError,
    ConfigurationTrustHardeningService,
)


def payload(workspace: str = "ws-a", source: str = "src-1", blocked: bool = False) -> TrustAssessmentCreate:
    return TrustAssessmentCreate(
        workspace_id=workspace,
        source_key=source,
        rollback_assessment_id="rb-1",
        nodes=[
            TrustNode(node_id="cfg", node_type="configuration", version="2.0", digest="digest-config", evidence_ref="ev-cfg", verified=True),
            TrustNode(node_id="runtime", node_type="runtime", version="2.0", digest="digest-runtime", evidence_ref="ev-runtime", verified=True),
        ],
        edges=[TrustEdge(edge_id="e1", source_node_id="cfg", target_node_id="runtime", relation="deployed-as", confidence=0.95, evidence_ref="ev-edge")],
        controls=[HardeningControl(control_id="ctl-1", name="tighten restart guard", current_value="2", proposed_value="1", expected_risk_reduction=0.4, evidence_ref="ev-control")],
        provenance_evidence_refs=["prov-1"],
        runtime_evidence_refs=["run-1"],
        risk_decision=RiskDecision.BLOCK if blocked else RiskDecision.ALLOW,
    )


def test_full_trust_hardening_lifecycle() -> None:
    service = ConfigurationTrustHardeningService()
    record = service.create(payload())
    record = service.act(record.record_id, "ws-a", TrustActionRequest(action="score", actor="system"))
    assert record.trust_score > 90
    record = service.act(record.record_id, "ws-a", TrustActionRequest(action="request-review", actor="reviewer"))
    record = service.act(record.record_id, "ws-a", TrustActionRequest(action="approve", actor="reviewer", approval_token="approve-1"))
    record = service.act(record.record_id, "ws-a", TrustActionRequest(action="queue-hardening", actor="orchestrator", receipt_id="queue-1"))
    record = service.act(record.record_id, "ws-a", TrustActionRequest(action="apply-hardening", actor="runtime", receipt_id="apply-1", applied_control_ids=["ctl-1"]))
    record = service.act(record.record_id, "ws-a", TrustActionRequest(action="verify", actor="verifier", receipt_id="verify-1", verification_evidence_refs=["verify-evidence"]))
    assert record.state == TrustState.VERIFIED
    assert len(service.audit("ws-a")) == 7


def test_risk_block_and_replay_protection() -> None:
    service = ConfigurationTrustHardeningService()
    blocked = service.create(payload(blocked=True))
    with pytest.raises(ConfigurationTrustHardeningError):
        service.act(blocked.record_id, "ws-a", TrustActionRequest(action="score", actor="system"))

    record = service.create(payload(source="src-2"))
    service.act(record.record_id, "ws-a", TrustActionRequest(action="score", actor="system"))
    service.act(record.record_id, "ws-a", TrustActionRequest(action="request-review", actor="reviewer"))
    service.act(record.record_id, "ws-a", TrustActionRequest(action="approve", actor="reviewer", approval_token="token"))

    other = service.create(payload(source="src-3"))
    service.act(other.record_id, "ws-a", TrustActionRequest(action="score", actor="system"))
    service.act(other.record_id, "ws-a", TrustActionRequest(action="request-review", actor="reviewer"))
    with pytest.raises(ConfigurationTrustHardeningError):
        service.act(other.record_id, "ws-a", TrustActionRequest(action="approve", actor="reviewer", approval_token="token"))


def test_duplicate_sources_graph_integrity_and_workspace_isolation() -> None:
    service = ConfigurationTrustHardeningService()
    record = service.create(payload())
    with pytest.raises(ConfigurationTrustHardeningError):
        service.create(payload())
    with pytest.raises(ConfigurationTrustHardeningError):
        service.get(record.record_id, "ws-b")

    with pytest.raises(ValueError):
        TrustAssessmentCreate(
            **payload(source="bad").model_dump(exclude={"edges"}),
            edges=[TrustEdge(edge_id="bad", source_node_id="missing", target_node_id="runtime", relation="deployed-as", confidence=0.5, evidence_ref="bad")],
        )


def test_all_controls_required_before_verification() -> None:
    service = ConfigurationTrustHardeningService()
    record = service.create(payload())
    service.act(record.record_id, "ws-a", TrustActionRequest(action="score", actor="system"))
    service.act(record.record_id, "ws-a", TrustActionRequest(action="request-review", actor="reviewer"))
    service.act(record.record_id, "ws-a", TrustActionRequest(action="approve", actor="reviewer", approval_token="a"))
    service.act(record.record_id, "ws-a", TrustActionRequest(action="queue-hardening", actor="orchestrator", receipt_id="q"))
    with pytest.raises(ConfigurationTrustHardeningError):
        service.act(record.record_id, "ws-a", TrustActionRequest(action="apply-hardening", actor="runtime", receipt_id="x", applied_control_ids=[]))
