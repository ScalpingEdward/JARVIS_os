import pytest
from pydantic import ValidationError

from backend.app.modules.strategic_portfolio_coordination.models import (
    AllocationAction,
    AllocationInstruction,
    PortfolioActionRequest,
    PortfolioSleeve,
    PortfolioState,
    RiskDecision,
    StrategicPortfolioCreate,
)
from backend.app.modules.strategic_portfolio_coordination.service import StrategicPortfolioError, StrategicPortfolioService


def payload(workspace: str = "ws") -> StrategicPortfolioCreate:
    sleeves = [
        PortfolioSleeve(sleeve_id="s1", mission_id="m1", strategy_id="alpha", account_id="a1", broker_id="b1", current_allocation=40000, maximum_allocation=60000, risk_budget=0.08, evidence_refs=["e1"]),
        PortfolioSleeve(sleeve_id="s2", mission_id="m2", strategy_id="beta", account_id="a2", broker_id="b2", current_allocation=30000, maximum_allocation=50000, risk_budget=0.08, evidence_refs=["e2"]),
    ]
    instructions = [
        AllocationInstruction(instruction_id="i1", sleeve_id="s1", action=AllocationAction.INCREASE, target_allocation=50000, rationale="stronger performance", confidence=0.9, evidence_refs=["r1"]),
        AllocationInstruction(instruction_id="i2", sleeve_id="s2", action=AllocationAction.DECREASE, target_allocation=25000, rationale="reduce concentration", confidence=0.9, evidence_refs=["r2"]),
    ]
    return StrategicPortfolioCreate(workspace_id=workspace, source_key="portfolio-1", portfolio_name="master", strategic_mission_ids=["m1", "m2"], total_capital=100000, sleeves=sleeves, instructions=instructions, portfolio_evidence_refs=["portfolio-evidence"])


def act(service, record, action, **kwargs):
    return service.act(record.record_id, record.workspace_id, PortfolioActionRequest(action=action, actor="tester", **kwargs))


def test_full_allocation_and_balancing_lifecycle():
    service = StrategicPortfolioService()
    record = service.create(payload())
    act(service, record, "prepare-evidence")
    act(service, record, "evaluate")
    act(service, record, "propose-rebalance", instruction_ids=["i1", "i2"])
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="approval-1")
    act(service, record, "allocate", receipt_id="allocate-1", evidence_refs=["allocation-proof"])
    for index in range(3):
        act(service, record, "record-cycle", receipt_id=f"cycle-{index}", cycle_healthy=True, portfolio_drawdown=0.02, evidence_refs=[f"cycle-evidence-{index}"])
    act(service, record, "confirm-balanced", receipt_id="balanced-1")
    assert record.state == PortfolioState.BALANCED
    assert record.sleeves[0].current_allocation == 50000


def test_drawdown_escalates_portfolio():
    service = StrategicPortfolioService()
    record = service.create(payload())
    for action, kwargs in [("prepare-evidence", {}), ("evaluate", {}), ("propose-rebalance", {"instruction_ids": ["i1"]}), ("request-review", {}), ("approve", {"approval_token": "a"}), ("allocate", {"receipt_id": "r"})]:
        act(service, record, action, **kwargs)
    act(service, record, "record-cycle", receipt_id="bad-cycle", cycle_healthy=False, portfolio_drawdown=0.2, evidence_refs=["dd-proof"])
    assert record.state == PortfolioState.ESCALATED


def test_risk_block_and_receipt_replay():
    service = StrategicPortfolioService()
    blocked = service.create(payload("blocked").model_copy(update={"source_key": "blocked", "risk_decision": RiskDecision.BLOCK}))
    act(service, blocked, "prepare-evidence")
    assert blocked.state == PortfolioState.BLOCKED

    record = service.create(payload().model_copy(update={"source_key": "second"}))
    act(service, record, "prepare-evidence")
    act(service, record, "evaluate")
    act(service, record, "propose-rebalance", instruction_ids=["i1"])
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="unique")
    act(service, record, "allocate", receipt_id="receipt")
    with pytest.raises(StrategicPortfolioError):
        act(service, record, "record-cycle", receipt_id="receipt", cycle_healthy=True)


def test_duplicate_sleeves_and_unknown_instruction_rejected():
    base = payload()
    with pytest.raises(ValidationError):
        StrategicPortfolioCreate(**base.model_dump() | {"sleeves": [base.sleeves[0], base.sleeves[0]]})
    bad_instruction = AllocationInstruction(instruction_id="bad", sleeve_id="missing", action=AllocationAction.HOLD, target_allocation=0, rationale="bad", confidence=1, evidence_refs=["e"])
    with pytest.raises(ValidationError):
        StrategicPortfolioCreate(**base.model_dump() | {"instructions": [bad_instruction]})


def test_workspace_isolation_and_allocation_ceiling():
    service = StrategicPortfolioService()
    record = service.create(payload())
    with pytest.raises(StrategicPortfolioError):
        service.get(record.record_id, "other")

    oversized = payload().model_copy(update={"source_key": "oversized", "instructions": [AllocationInstruction(instruction_id="big", sleeve_id="s1", action=AllocationAction.INCREASE, target_allocation=70000, rationale="too large", confidence=0.95, evidence_refs=["x"])]})
    second = service.create(oversized)
    act(service, second, "prepare-evidence")
    act(service, second, "evaluate")
    with pytest.raises(StrategicPortfolioError):
        act(service, second, "propose-rebalance", instruction_ids=["big"])
