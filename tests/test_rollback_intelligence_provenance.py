import pytest

from backend.app.modules.rollback_intelligence_provenance.models import (
    ProvenanceNode,
    RiskDecision,
    RollbackActionRequest,
    RollbackAssessmentCreate,
    RollbackSignal,
    RollbackState,
)
from backend.app.modules.rollback_intelligence_provenance.service import (
    RollbackIntelligenceError,
    RollbackIntelligenceService,
)


def payload(workspace: str = "alpha", source: str = "deployment-1", risk=RiskDecision.ALLOW):
    return RollbackAssessmentCreate(
        workspace_id=workspace,
        source_key=source,
        deployment_verification_id="verify-30-1",
        current=ProvenanceNode(
            version="config-31",
            artifact_digest="sha256:current123456",
            parent_version="config-30",
            deployed_at="2026-07-22T12:00:00Z",
            source_ref="rollout-29-1",
            runtime_ids=["runtime-a"],
        ),
        rollback_target=ProvenanceNode(
            version="config-30",
            artifact_digest="sha256:rollback123456",
            deployed_at="2026-07-21T12:00:00Z",
            source_ref="verification-30-0",
            runtime_ids=["runtime-a"],
        ),
        signals=[
            RollbackSignal(signal_id="errors", name="error rate", baseline=1, observed=3,
                           weight=0.6, deterioration_direction="higher", critical=True,
                           evidence_ref="metric:error-rate"),
            RollbackSignal(signal_id="latency", name="latency", baseline=100, observed=130,
                           weight=0.4, deterioration_direction="higher",
                           evidence_ref="metric:latency"),
        ],
        deployment_evidence_refs=["deployment:verified"],
        runtime_evidence_refs=["runtime:healthy-before"],
        risk_decision=risk,
    )


def action(name: str, **kwargs):
    return RollbackActionRequest(action=name, actor="operator", **kwargs)


def test_full_rollback_lifecycle():
    service = RollbackIntelligenceService()
    record = service.create(payload())
    record = service.act("alpha", record.record_id, action("analyze"))
    assert record.state == RollbackState.ANALYZED
    assert record.recommendation == "rollback"
    assert record.critical_signal_count == 1
    record = service.act("alpha", record.record_id, action("request-review"))
    record = service.act("alpha", record.record_id, action("approve", approval_token="approval-1"))
    record = service.act("alpha", record.record_id, action("queue-rollback", receipt_id="queue-1"))
    record = service.act("alpha", record.record_id, action("execute-rollback", receipt_id="execute-1"))
    record = service.act("alpha", record.record_id, action(
        "verify", receipt_id="verify-1", verification_evidence_refs=["runtime:config-30-restored"]
    ))
    assert record.state == RollbackState.VERIFIED
    assert len(service.audit("alpha")) == 7


def test_risk_hard_block():
    service = RollbackIntelligenceService()
    record = service.create(payload(risk=RiskDecision.BLOCK))
    assert record.state == RollbackState.BLOCKED
    with pytest.raises(RollbackIntelligenceError, match="hard block"):
        service.act("alpha", record.record_id, action("analyze"))


def test_replay_protection_and_duplicate_source():
    service = RollbackIntelligenceService()
    first = service.create(payload())
    with pytest.raises(RollbackIntelligenceError, match="duplicate source_key"):
        service.create(payload())
    service.act("alpha", first.record_id, action("analyze"))
    service.act("alpha", first.record_id, action("request-review"))
    service.act("alpha", first.record_id, action("approve", approval_token="same-token"))
    second = service.create(payload(source="deployment-2"))
    service.act("alpha", second.record_id, action("analyze"))
    service.act("alpha", second.record_id, action("request-review"))
    with pytest.raises(RollbackIntelligenceError, match="replay"):
        service.act("alpha", second.record_id, action("approve", approval_token="same-token"))


def test_workspace_isolation_and_verification_evidence():
    service = RollbackIntelligenceService()
    record = service.create(payload())
    with pytest.raises(RollbackIntelligenceError, match="not found"):
        service.get("other", record.record_id)
    for request in [
        action("analyze"), action("request-review"),
        action("approve", approval_token="a"), action("queue-rollback", receipt_id="q"),
        action("execute-rollback", receipt_id="e"),
    ]:
        record = service.act("alpha", record.record_id, request)
    with pytest.raises(RollbackIntelligenceError, match="verification evidence"):
        service.act("alpha", record.record_id, action("verify", receipt_id="v"))
