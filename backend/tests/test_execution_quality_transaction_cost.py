import pytest

from app.schemas.execution_quality_transaction_cost import (
    ExecutionAction,
    ExecutionRecordCreate,
    ExecutionState,
)
from app.services.execution_quality_transaction_cost import ExecutionQualityService


@pytest.fixture
def service() -> ExecutionQualityService:
    return ExecutionQualityService()


def payload(workspace: str = "ws-a", source_key: str = "order-1") -> ExecutionRecordCreate:
    return ExecutionRecordCreate(
        workspace_id=workspace,
        source_key=source_key,
        requested_by="analyst",
        observations=[
            {
                "venue": "venue-a",
                "symbol": "XAUUSD",
                "side": "buy",
                "order_type": "market",
                "requested_quantity": 10,
                "filled_quantity": 10,
                "arrival_price": 2400,
                "average_fill_price": 2400.6,
                "benchmark_price": 2400.3,
                "explicit_fees_bps": 0.4,
                "latency_ms": 85,
                "participation_rate": 0.08,
                "confidence": 0.95,
                "freshness": 0.98,
                "provenance": ["broker-fill", "venue-tape"],
            }
        ],
    )


def test_scores_execution_record(service: ExecutionQualityService) -> None:
    record = service.create(payload())
    assert record.state in {ExecutionState.SCORED, ExecutionState.REVIEW_REQUIRED}
    assert record.scores.fill_rate == 1
    assert 0 <= record.scores.execution_quality <= 100


def test_duplicate_source_key_is_rejected_per_workspace(service: ExecutionQualityService) -> None:
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.create(payload("ws-b")).workspace_id == "ws-b"


def test_workspace_isolation(service: ExecutionQualityService) -> None:
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get(record.record_id, "ws-b")


def test_human_approval_and_replay_protection(service: ExecutionQualityService) -> None:
    record = service.create(payload())
    action = ExecutionAction(action="approve", actor="risk-officer", operation_id="op-1")
    approved = service.act(record.record_id, "ws-a", action)
    replayed = service.act(record.record_id, "ws-a", action)
    assert approved.state == ExecutionState.APPROVED
    assert replayed.version == approved.version
    assert approved.approved_by == "risk-officer"


def test_risk_brain_hard_block_is_authoritative(service: ExecutionQualityService) -> None:
    record = service.create(payload())
    blocked = service.act(
        record.record_id,
        "ws-a",
        ExecutionAction(action="activate", actor="operator", operation_id="op-block"),
        risk_blocked=True,
    )
    assert blocked.state == ExecutionState.BLOCKED
    assert "risk-brain-hard-block" in blocked.risk_flags


def test_module_never_enables_execution(service: ExecutionQualityService) -> None:
    assert service.status()["execution_enabled"] is False
