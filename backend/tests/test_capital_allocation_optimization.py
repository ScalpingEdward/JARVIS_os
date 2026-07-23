import pytest

from app.schemas.capital_allocation_optimization import (
    AllocationAction,
    AllocationRecordCreate,
    AllocationState,
)
from app.services.capital_allocation_optimization import CapitalAllocationOptimizationService


@pytest.fixture
def service() -> CapitalAllocationOptimizationService:
    return CapitalAllocationOptimizationService()


def payload(workspace: str = "ws-a", source_key: str = "allocation-1") -> AllocationRecordCreate:
    return AllocationRecordCreate(
        workspace_id=workspace,
        source_key=source_key,
        requested_by="portfolio-analyst",
        max_turnover=0.30,
        max_single_weight=0.50,
        min_liquidity_score=60,
        candidates=[
            {
                "sleeve": "macro",
                "current_weight": 0.45,
                "proposed_weight": 0.40,
                "expected_return": 0.12,
                "expected_volatility": 0.16,
                "expected_shortfall": 0.08,
                "liquidity_score": 88,
                "conviction": 0.82,
                "confidence": 0.94,
                "freshness": 0.98,
                "provenance": ["risk-engine", "performance-attribution"],
            },
            {
                "sleeve": "relative-value",
                "current_weight": 0.35,
                "proposed_weight": 0.35,
                "expected_return": 0.09,
                "expected_volatility": 0.10,
                "expected_shortfall": 0.05,
                "liquidity_score": 82,
                "conviction": 0.76,
                "confidence": 0.91,
                "freshness": 0.96,
                "provenance": ["cross-asset", "liquidity-intelligence"],
            },
            {
                "sleeve": "cash-buffer",
                "current_weight": 0.20,
                "proposed_weight": 0.25,
                "expected_return": 0.03,
                "expected_volatility": 0.02,
                "expected_shortfall": 0.01,
                "liquidity_score": 100,
                "conviction": 0.70,
                "confidence": 0.99,
                "freshness": 1,
                "provenance": ["treasury"],
            },
        ],
    )


def test_scores_allocation_record(service: CapitalAllocationOptimizationService) -> None:
    record = service.create(payload())
    assert record.state in {AllocationState.SCORED, AllocationState.REVIEW_REQUIRED}
    assert record.scores.constraint_compliance == 100
    assert 0 <= record.scores.diversification_score <= 100


def test_duplicate_source_key_is_rejected_per_workspace(service: CapitalAllocationOptimizationService) -> None:
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.create(payload("ws-b")).workspace_id == "ws-b"


def test_workspace_isolation(service: CapitalAllocationOptimizationService) -> None:
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get(record.record_id, "ws-b")


def test_human_approval_and_replay_protection(service: CapitalAllocationOptimizationService) -> None:
    record = service.create(payload())
    action = AllocationAction(action="approve", actor="risk-officer", operation_id="op-1")
    approved = service.act(record.record_id, "ws-a", action)
    replayed = service.act(record.record_id, "ws-a", action)
    assert approved.state == AllocationState.APPROVED
    assert replayed.version == approved.version
    assert approved.approved_by == "risk-officer"


def test_risk_brain_hard_block_is_authoritative(service: CapitalAllocationOptimizationService) -> None:
    record = service.create(payload())
    blocked = service.act(
        record.record_id,
        "ws-a",
        AllocationAction(action="activate", actor="operator", operation_id="op-block"),
        risk_blocked=True,
    )
    assert blocked.state == AllocationState.BLOCKED
    assert "risk-brain-hard-block" in blocked.risk_flags


def test_module_never_mutates_allocations_or_executes(service: CapitalAllocationOptimizationService) -> None:
    status = service.status()
    assert status["allocation_mutation_enabled"] is False
    assert status["execution_enabled"] is False
