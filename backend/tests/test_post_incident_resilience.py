import pytest

from app.modules.post_incident_resilience.models import (
    FindingSeverity,
    ResilienceFinding,
    ResilienceMetric,
    ResilienceReviewAction,
    ResilienceReviewCreate,
    ReviewState,
)
from app.modules.post_incident_resilience.service import (
    PostIncidentResilienceError,
    PostIncidentResilienceService,
)


def payload(**overrides):
    values = {
        "workspace_id": "ws-1",
        "source_key": "review-1",
        "incident_record_id": "incident-1",
        "reconciliation_record_id": "recon-1",
        "runtime_record_id": "runtime-1",
        "upstream_evidence_verified": True,
        "root_cause": "Broker session degradation caused delayed acknowledgements.",
        "impact_summary": "Execution confirmation was delayed without capital loss.",
        "findings": [
            ResilienceFinding(
                finding_id="f-1",
                category="runtime",
                severity=FindingSeverity.CRITICAL,
                description="Heartbeat threshold was too permissive.",
                evidence_refs=["incident-1", "runtime-1"],
                recommended_action="Reduce heartbeat timeout and add a regional failover.",
            ),
            ResilienceFinding(
                finding_id="f-2",
                category="monitoring",
                severity=FindingSeverity.WARNING,
                description="Alert escalation lacked an intermediate warning.",
                recommended_action="Add a degraded-state warning before circuit opening.",
            ),
        ],
        "metrics": [
            ResilienceMetric(name="recovery-time", baseline_value=180, observed_value=240, target_value=120, unit="seconds")
        ],
    }
    values.update(overrides)
    return ResilienceReviewCreate(**values)


def test_full_review_improvement_and_verification_lifecycle():
    service = PostIncidentResilienceService()
    record = service.create(payload())
    assert record.state == ReviewState.DRAFT

    record = service.act(record.record_id, "ws-1", ResilienceReviewAction(action="analyze", actor_id="system"))
    assert record.state == ReviewState.HUMAN_REVIEW_REQUIRED
    assert record.critical_findings == 1
    assert 0 <= record.resilience_score <= 100

    record = service.act(
        record.record_id,
        "ws-1",
        ResilienceReviewAction(action="approve", actor_id="operator", approval_token="approval-1"),
    )
    assert record.state == ReviewState.APPROVED

    record = service.act(
        record.record_id,
        "ws-1",
        ResilienceReviewAction(action="queue-improvement", actor_id="operator", receipt_id="queue-1"),
    )
    assert record.state == ReviewState.IMPROVEMENT_QUEUED

    with pytest.raises(PostIncidentResilienceError, match="all resilience findings"):
        service.act(
            record.record_id,
            "ws-1",
            ResilienceReviewAction(
                action="verify",
                actor_id="reviewer",
                receipt_id="verify-incomplete",
                completed_finding_ids=["f-1"],
            ),
        )

    record = service.act(
        record.record_id,
        "ws-1",
        ResilienceReviewAction(
            action="verify",
            actor_id="reviewer",
            receipt_id="verify-complete",
            completed_finding_ids=["f-1", "f-2"],
        ),
    )
    assert record.state == ReviewState.VERIFIED
    assert record.completed_finding_ids == ["f-1", "f-2"]

    record = service.act(record.record_id, "ws-1", ResilienceReviewAction(action="archive", actor_id="operator"))
    assert record.state == ReviewState.ARCHIVED


def test_hard_gates_replay_protection_and_workspace_isolation():
    service = PostIncidentResilienceService()
    assert service.create(payload(source_key="blocked", risk_brain_blocked=True)).state == ReviewState.BLOCKED
    assert service.create(payload(source_key="missing", upstream_evidence_verified=False)).state == ReviewState.EVIDENCE_REQUIRED

    record = service.create(payload())
    service.act(record.record_id, "ws-1", ResilienceReviewAction(action="analyze", actor_id="system"))
    service.act(
        record.record_id,
        "ws-1",
        ResilienceReviewAction(action="approve", actor_id="operator", approval_token="token"),
    )

    second = service.create(payload(source_key="review-2"))
    service.act(second.record_id, "ws-1", ResilienceReviewAction(action="analyze", actor_id="system"))
    with pytest.raises(PostIncidentResilienceError, match="replay"):
        service.act(
            second.record_id,
            "ws-1",
            ResilienceReviewAction(action="approve", actor_id="operator", approval_token="token"),
        )

    service.act(
        record.record_id,
        "ws-1",
        ResilienceReviewAction(action="queue-improvement", actor_id="operator", receipt_id="receipt"),
    )
    with pytest.raises(PostIncidentResilienceError, match="replay"):
        service.act(
            record.record_id,
            "ws-1",
            ResilienceReviewAction(
                action="verify",
                actor_id="reviewer",
                receipt_id="receipt",
                completed_finding_ids=["f-1", "f-2"],
            ),
        )
    with pytest.raises(PostIncidentResilienceError, match="not found"):
        service.get(record.record_id, "ws-2")


def test_duplicate_source_and_findings_rejected():
    service = PostIncidentResilienceService()
    service.create(payload())
    with pytest.raises(PostIncidentResilienceError, match="duplicate source"):
        service.create(payload())
    with pytest.raises(ValueError, match="duplicate resilience finding"):
        payload(
            source_key="duplicate-findings",
            findings=[
                ResilienceFinding(
                    finding_id="x",
                    category="runtime",
                    severity=FindingSeverity.INFO,
                    description="one",
                    recommended_action="one",
                ),
                ResilienceFinding(
                    finding_id="x",
                    category="runtime",
                    severity=FindingSeverity.WARNING,
                    description="two",
                    recommended_action="two",
                ),
            ],
        )
