import pytest
from pydantic import ValidationError

from backend.app.modules.treasury_liquidity_governance.models import FundingAction, FundingInstruction, RiskDecision, TreasuryAccount, TreasuryActionRequest, TreasuryCreate, TreasuryState
from backend.app.modules.treasury_liquidity_governance.service import TreasuryGovernanceError, TreasuryGovernanceService


def payload(workspace: str = "ws") -> TreasuryCreate:
    accounts = [
        TreasuryAccount(account_id="a1", provider_id="broker-a", currency="USD", available_balance=60000, reserved_balance=10000, minimum_operating_balance=5000, maximum_exposure=90000, evidence_refs=["a1-e"]),
        TreasuryAccount(account_id="a2", provider_id="broker-b", currency="USD", available_balance=30000, reserved_balance=0, minimum_operating_balance=5000, maximum_exposure=50000, evidence_refs=["a2-e"]),
    ]
    instructions = [
        FundingInstruction(instruction_id="f1", action=FundingAction.TRANSFER, source_account_id="a1", target_account_id="a2", amount=5000, currency="USD", rationale="rebalance liquidity", confidence=0.9, evidence_refs=["f1-e"])
    ]
    return TreasuryCreate(workspace_id=workspace, source_key="portfolio-1", portfolio_record_id="p1", treasury_name="main", accounts=accounts, instructions=instructions, maximum_total_exposure=150000, maximum_single_provider_weight=0.8, treasury_evidence_refs=["treasury-e"])


def act(service, record, action, **kwargs):
    return service.act(record.record_id, record.workspace_id, TreasuryActionRequest(action=action, actor="tester", **kwargs))


def test_full_funding_lifecycle():
    service = TreasuryGovernanceService()
    record = service.create(payload())
    act(service, record, "prepare-evidence")
    act(service, record, "evaluate")
    act(service, record, "propose-funding", instruction_ids=["f1"])
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="a1")
    act(service, record, "execute-funding", receipt_id="r1", evidence_refs=["execution"])
    for index in range(3):
        act(service, record, "record-cycle", receipt_id=f"c{index}", cycle_healthy=True, liquidity_ratio=0.8, total_exposure=100000, evidence_refs=[f"e{index}"])
    act(service, record, "confirm-liquid", receipt_id="done")
    assert record.state == TreasuryState.LIQUID


def test_liquidity_escalation_and_replay():
    service = TreasuryGovernanceService()
    record = service.create(payload())
    for action, kwargs in [("prepare-evidence", {}), ("evaluate", {}), ("propose-funding", {"instruction_ids": ["f1"]}), ("request-review", {}), ("approve", {"approval_token": "approval"}), ("execute-funding", {"receipt_id": "fund"})]:
        act(service, record, action, **kwargs)
    act(service, record, "record-cycle", receipt_id="cycle", cycle_healthy=False, liquidity_ratio=0.1, total_exposure=100000)
    assert record.state == TreasuryState.ESCALATED
    with pytest.raises(TreasuryGovernanceError):
        act(service, record, "revoke", receipt_id="cycle")


def test_risk_block_and_workspace_isolation():
    service = TreasuryGovernanceService()
    blocked = service.create(payload("blocked").model_copy(update={"source_key": "blocked", "risk_decision": RiskDecision.BLOCK}))
    act(service, blocked, "prepare-evidence")
    assert blocked.state == TreasuryState.BLOCKED
    record = service.create(payload().model_copy(update={"source_key": "second"}))
    with pytest.raises(TreasuryGovernanceError):
        service.get(record.record_id, "other")


def test_duplicate_account_ids_rejected():
    base = payload()
    with pytest.raises(ValidationError):
        TreasuryCreate(**base.model_dump() | {"accounts": [base.accounts[0], base.accounts[0]]})
