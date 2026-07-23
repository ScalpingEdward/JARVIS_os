import pytest
from pydantic import ValidationError

from backend.app.modules.settlement_custody_reconciliation.models import (
    CustodyPosition,
    ReconciliationInstruction,
    RiskDecision,
    SettlementActionRequest,
    SettlementCreate,
    SettlementItem,
    SettlementState,
    SettlementStatus,
)
from backend.app.modules.settlement_custody_reconciliation.service import SettlementGovernanceError, SettlementGovernanceService


def payload(workspace: str = "ws") -> SettlementCreate:
    return SettlementCreate(
        workspace_id=workspace,
        source_key="treasury-1",
        treasury_record_id="tr-1",
        ledger_name="primary-ledger",
        positions=[CustodyPosition(position_id="p1", account_id="a1", custodian_id="c1", asset="USD", internal_quantity=1000, external_quantity=1000, evidence_refs=["pos-e1"])],
        settlements=[SettlementItem(settlement_id="s1", provider_id="prov", source_account_id="a1", target_account_id="a2", asset="USD", amount=100, expected_fee=1, evidence_refs=["set-e1"])],
        instructions=[ReconciliationInstruction(instruction_id="i1", position_id="p1", expected_delta=0, rationale="ledger aligned", confidence=0.95, evidence_refs=["rec-e1"])],
        maximum_unreconciled_value=0,
        settlement_evidence_refs=["evidence-1"],
    )


def act(service, record, action, **kwargs):
    return service.act(record.record_id, record.workspace_id, SettlementActionRequest(action=action, actor="tester", **kwargs))


def test_full_settlement_reconciliation_lifecycle():
    service = SettlementGovernanceService()
    record = service.create(payload())
    act(service, record, "prepare-evidence")
    act(service, record, "evaluate")
    act(service, record, "propose-reconciliation", instruction_ids=["i1"])
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="a1")
    act(service, record, "start-settlement", receipt_id="r1")
    act(service, record, "record-settlement", receipt_id="r2", settlement_id="s1", settlement_status=SettlementStatus.SETTLED, actual_fee=1, evidence_refs=["settled"])
    act(service, record, "start-reconciliation", receipt_id="r3")
    for index in range(3):
        act(service, record, "record-cycle", receipt_id=f"c{index}", cycle_healthy=True, unreconciled_value=0, evidence_refs=[f"cycle-{index}"])
    act(service, record, "confirm-reconciled", receipt_id="done")
    assert record.state == SettlementState.RECONCILED


def test_failed_settlement_escalates():
    service = SettlementGovernanceService()
    record = service.create(payload())
    for action, kwargs in [
        ("prepare-evidence", {}),
        ("evaluate", {}),
        ("propose-reconciliation", {"instruction_ids": ["i1"]}),
        ("request-review", {}),
        ("approve", {"approval_token": "a"}),
        ("start-settlement", {"receipt_id": "start"}),
    ]:
        act(service, record, action, **kwargs)
    act(service, record, "record-settlement", receipt_id="failed", settlement_id="s1", settlement_status=SettlementStatus.FAILED, actual_fee=1)
    assert record.state == SettlementState.ESCALATED


def test_risk_block_replay_and_isolation():
    service = SettlementGovernanceService()
    blocked = service.create(payload("blocked").model_copy(update={"source_key": "blocked", "risk_decision": RiskDecision.BLOCK}))
    act(service, blocked, "prepare-evidence")
    assert blocked.state == SettlementState.BLOCKED

    record = service.create(payload().model_copy(update={"source_key": "second"}))
    act(service, record, "prepare-evidence")
    act(service, record, "evaluate")
    act(service, record, "propose-reconciliation", instruction_ids=["i1"])
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="unique")
    with pytest.raises(SettlementGovernanceError):
        other = service.create(payload("other").model_copy(update={"source_key": "other"}))
        other.state = SettlementState.HUMAN_REVIEW_REQUIRED
        act(service, other, "approve", approval_token="unique")
    with pytest.raises(SettlementGovernanceError):
        service.get(record.record_id, "other")


def test_duplicate_position_ids_rejected():
    position = payload().positions[0]
    with pytest.raises(ValidationError):
        SettlementCreate(**payload().model_dump() | {"positions": [position.model_dump(), position.model_dump()]})
