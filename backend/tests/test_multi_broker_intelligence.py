import pytest

from app.schemas.multi_broker_intelligence import MultiBrokerAction, MultiBrokerCreate, MultiBrokerState
from app.services.multi_broker_intelligence import (
    MultiBrokerConflictError,
    MultiBrokerIntelligenceService,
    MultiBrokerNotFoundError,
    MultiBrokerPolicyError,
)


def payload(workspace_id: str = "ws-a", source_key: str = "snapshot-1") -> MultiBrokerCreate:
    return MultiBrokerCreate(
        workspace_id=workspace_id,
        source_key=source_key,
        requested_by="risk-analyst",
        max_broker_weight=0.6,
        observations=[
            {
                "broker_id": "broker-a",
                "venue_type": "prime-broker",
                "asset_class": "fx",
                "quoted_spread_bps": 1.2,
                "realized_spread_bps": 1.5,
                "median_latency_ms": 28,
                "p95_latency_ms": 70,
                "fill_rate": 0.99,
                "rejection_rate": 0.005,
                "slippage_bps": 0.4,
                "partial_fill_rate": 0.01,
                "uptime": 0.999,
                "liquidity_score": 0.94,
                "counterparty_score": 0.92,
                "regulatory_score": 0.96,
                "capacity_utilization": 0.35,
                "current_routing_weight": 0.55,
                "confidence": 0.98,
                "freshness": 0.99,
                "provenance": ["broker-tca", "uptime-monitor"],
            },
            {
                "broker_id": "broker-b",
                "venue_type": "ecn",
                "asset_class": "fx",
                "quoted_spread_bps": 1.0,
                "realized_spread_bps": 1.8,
                "median_latency_ms": 45,
                "p95_latency_ms": 110,
                "fill_rate": 0.975,
                "rejection_rate": 0.012,
                "slippage_bps": 0.7,
                "partial_fill_rate": 0.03,
                "uptime": 0.997,
                "liquidity_score": 0.90,
                "counterparty_score": 0.86,
                "regulatory_score": 0.90,
                "capacity_utilization": 0.55,
                "current_routing_weight": 0.45,
                "confidence": 0.95,
                "freshness": 0.97,
                "provenance": ["broker-tca"],
            },
        ],
    )


def test_scoring_normalizes_advisory_weights_and_preserves_safety_boundary() -> None:
    service = MultiBrokerIntelligenceService()
    record = service.create(payload())

    assert record.state == MultiBrokerState.SCORED
    assert round(sum(item.recommended_routing_weight for item in record.recommendations), 6) == 1
    assert max(item.recommended_routing_weight for item in record.recommendations) <= 0.6
    assert record.scores.aggregate_execution_quality > 0.7

    module_status = service.status()
    assert module_status["governance_only"] is True
    assert module_status["routing_mutation_enabled"] is False
    assert module_status["broker_configuration_mutation_enabled"] is False
    assert module_status["fund_movement_enabled"] is False
    assert module_status["execution_enabled"] is False


def test_detects_counterparty_latency_and_capacity_risk() -> None:
    service = MultiBrokerIntelligenceService()
    risky = payload(source_key="risky")
    risky.observations[0].counterparty_score = 0.4
    risky.observations[0].p95_latency_ms = 500
    risky.observations[0].capacity_utilization = 0.95

    record = service.create(risky)

    assert record.state == MultiBrokerState.COUNTERPARTY_ALERT
    assert "counterparty:broker-a" in record.risk_flags
    assert "latency:broker-a" in record.risk_flags
    assert "capacity:broker-a" in record.risk_flags
    broker = next(item for item in record.recommendations if item.broker_id == "broker-a")
    assert broker.routing_signal == "suspend-routing"
    assert broker.recommended_routing_weight == 0


def test_duplicate_source_and_operation_replay_are_blocked() -> None:
    service = MultiBrokerIntelligenceService()
    record = service.create(payload())

    with pytest.raises(MultiBrokerConflictError):
        service.create(payload())

    service.action(
        "ws-a",
        record.record_id,
        MultiBrokerAction(action="submit-review", actor="reviewer", operation_id="op-1"),
    )
    with pytest.raises(MultiBrokerConflictError):
        service.action(
            "ws-a",
            record.record_id,
            MultiBrokerAction(action="submit-review", actor="reviewer", operation_id="op-1"),
        )


def test_human_approval_and_risk_brain_hard_block() -> None:
    service = MultiBrokerIntelligenceService()
    record = service.create(payload())

    with pytest.raises(MultiBrokerPolicyError):
        service.action(
            "ws-a",
            record.record_id,
            MultiBrokerAction(action="activate", actor="operator", operation_id="activate-early"),
        )

    review = service.action(
        "ws-a",
        record.record_id,
        MultiBrokerAction(action="submit-review", actor="reviewer", operation_id="review-1"),
    )
    assert review.state == MultiBrokerState.REVIEW_REQUIRED

    service.risk_brain_blocked = True
    with pytest.raises(MultiBrokerPolicyError):
        service.action(
            "ws-a",
            record.record_id,
            MultiBrokerAction(action="approve", actor="risk-officer", operation_id="approve-blocked"),
        )

    service.risk_brain_blocked = False
    approved = service.action(
        "ws-a",
        record.record_id,
        MultiBrokerAction(action="approve", actor="risk-officer", operation_id="approve-1"),
    )
    active = service.action(
        "ws-a",
        record.record_id,
        MultiBrokerAction(action="activate", actor="operator", operation_id="activate-1"),
    )
    assert approved.approved_by == "risk-officer"
    assert active.state == MultiBrokerState.ACTIVE


def test_workspace_isolation_and_audit_trail() -> None:
    service = MultiBrokerIntelligenceService()
    record = service.create(payload())

    assert service.list("ws-b") == []
    assert service.audit("ws-b") == []
    with pytest.raises(MultiBrokerNotFoundError):
        service.get("ws-b", record.record_id)

    audit = service.audit("ws-a")
    assert len(audit) == 1
    assert audit[0]["action"] == "create"
    assert audit[0]["record_id"] == record.record_id
