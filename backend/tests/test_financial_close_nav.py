import pytest
from pydantic import ValidationError

from backend.app.modules.financial_close_nav.models import CloseActionRequest, CloseState, FinancialCloseCreate, RiskDecision, ValuationPosition, ValuationStatus
from backend.app.modules.financial_close_nav.service import FinancialCloseError, FinancialCloseService


def payload(workspace: str = "ws") -> FinancialCloseCreate:
    return FinancialCloseCreate(
        workspace_id=workspace,
        source_key="close-1",
        settlement_record_id="settlement-1",
        close_name="daily-close",
        reporting_currency="USD",
        positions=[ValuationPosition(position_id="p1", account_id="a1", asset="BTC", quantity=1, unit_price=100, market_value=100, evidence_refs=["price-1"])],
        cash_balance=20,
        liabilities=10,
        accrued_fees=2,
        maximum_nav_variance=0.02,
        maximum_stale_price_ratio=0.1,
        required_healthy_cycles=2,
        close_evidence_refs=["close-evidence"],
    )


def act(service, record, action, **kwargs):
    return service.act(record.record_id, record.workspace_id, CloseActionRequest(action=action, actor="tester", **kwargs))


def test_full_close_lifecycle():
    service = FinancialCloseService()
    record = service.create(payload())
    assert record.calculated_nav == 108
    act(service, record, "prepare-evidence")
    act(service, record, "calculate", external_nav=108)
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="a1")
    act(service, record, "close", receipt_id="r1", evidence_refs=["close-receipt"])
    for index in range(2):
        act(service, record, "record-cycle", receipt_id=f"v{index}", cycle_healthy=True, external_nav=108, evidence_refs=[f"e{index}"])
    act(service, record, "verify", receipt_id="verify")
    assert record.state == CloseState.VERIFIED


def test_stale_prices_escalate():
    service = FinancialCloseService()
    data = payload().model_copy(update={"positions": [payload().positions[0].model_copy(update={"valuation_status": ValuationStatus.STALE})]})
    record = service.create(data)
    act(service, record, "prepare-evidence")
    act(service, record, "calculate")
    assert record.state == CloseState.ESCALATED


def test_risk_and_replay_controls():
    service = FinancialCloseService()
    blocked = service.create(payload("blocked").model_copy(update={"source_key": "blocked", "risk_decision": RiskDecision.BLOCK}))
    act(service, blocked, "prepare-evidence")
    assert blocked.state == CloseState.BLOCKED

    record = service.create(payload().model_copy(update={"source_key": "second"}))
    for action, kwargs in [("prepare-evidence", {}), ("calculate", {}), ("request-review", {}), ("approve", {"approval_token": "token"})]:
        act(service, record, action, **kwargs)
    act(service, record, "close", receipt_id="receipt")
    with pytest.raises(FinancialCloseError):
        act(service, record, "record-cycle", receipt_id="receipt", cycle_healthy=True)


def test_duplicate_positions_rejected():
    position = payload().positions[0]
    with pytest.raises(ValidationError):
        FinancialCloseCreate(**payload().model_dump() | {"positions": [position.model_dump(), position.model_dump()]})


def test_workspace_isolation():
    service = FinancialCloseService()
    record = service.create(payload())
    with pytest.raises(FinancialCloseError):
        service.get(record.record_id, "other")
