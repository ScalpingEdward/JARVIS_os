"""Tests for the trade risk pipeline (approved setup -> real risk-sized recommendation)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.accounts.models import (
    AccountStateUpdate,
    AccountStatus,
    AccountType,
    PropFirmRules,
    StrategyAssignmentCreate,
    TradingAccountCreate,
)
from app.accounts.service import account_registry_service
from app.modules.dynamic_risk_engine.models import RiskState
from app.modules.execution_supervisor.models import SupervisionState
from app.modules.position_management_brain.models import PositionState
from app.setup_submission.service import setup_submission_service
from app.strategies.models import (
    FairValueGap,
    HTFBias,
    MarketSnapshot,
    OrderBlock,
    OrderBlockType,
    StructureLevel,
)
from app.setup_submission.models import SetupSubmissionRequest

from app.trade_risk_pipeline.models import RiskAssessmentRequest
from app.trade_risk_pipeline.service import TradeRiskPipelineError, trade_risk_pipeline_service

_LOGIN_SEQ = [20_000_000]


def _next_login() -> str:
    _LOGIN_SEQ[0] += 1
    return str(_LOGIN_SEQ[0])


def _snapshot(symbol: str = "EURUSD") -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        spread=0.00010,
        htf_bias=HTFBias.bullish,
        session="london",
        order_blocks=[
            OrderBlock(type=OrderBlockType.bullish, high=1.10010, low=1.09990, open=1.09990, close=1.10000)
        ],
        fvgs=[FairValueGap(side="bullish", top=1.10020, bottom=1.09980)],
        structure_levels=[
            StructureLevel(level=1.09900, type="low", strength=3),
            StructureLevel(level=1.10500, type="high", strength=4),
        ],
    )


def _register_account(*, prop_rules: PropFirmRules | None = None) -> UUID:
    login = _next_login()
    account = account_registry_service.register_account(
        TradingAccountCreate(
            label=f"Demo {login}",
            account_type=AccountType.prop,
            broker="TestBroker",
            login=login,
            server="Test-Server",
            currency="USD",
            initial_balance=100000.0,
            max_strategies=2,
            prop_rules=prop_rules or PropFirmRules(),
        )
    )
    account_registry_service.assign_strategy(
        account.id,
        StrategyAssignmentCreate(strategy_id="scalping_3tp", strategy_name="scalping_3tp", allocation_pct=100.0, enabled=True),
    )
    return account.id


def setup_function() -> None:
    account_registry_service.reset()
    setup_submission_service.reset()


def _submit_one_setup() -> UUID:
    account_id = _register_account()
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    assert report.total_submitted >= 1
    return report.submitted_setups[0].approval_request_id


def test_assess_unknown_approval_request_fails_closed() -> None:
    with pytest.raises(TradeRiskPipelineError, match="No pending/approved setup"):
        trade_risk_pipeline_service.assess(uuid4())


def test_assess_produces_a_real_position_size_from_stop_distance() -> None:
    approval_request_id = _submit_one_setup()
    record = trade_risk_pipeline_service.assess(
        approval_request_id, RiskAssessmentRequest(value_per_price_unit=10.0)
    )

    assert record.assessment.stop_distance > 0
    assert record.assessment.recommended_position_units > 0
    assert record.assessment.recommended_risk_amount > 0
    # Sizing must actually derive from stop distance, not be a fixed constant:
    # a smaller stop distance should recommend proportionally *more* units for
    # the same risk amount.
    assert (
        record.assessment.recommended_position_units
        == pytest.approx(record.assessment.recommended_risk_amount / (record.assessment.stop_distance * 10.0), rel=1e-6)
    )


def test_assess_on_suspended_account_fails_closed() -> None:
    approval_request_id = _submit_one_setup()
    setup = setup_submission_service.get_approval(approval_request_id)
    account_registry_service.suspend(setup.account_id)

    with pytest.raises(TradeRiskPipelineError, match="not active"):
        trade_risk_pipeline_service.assess(approval_request_id)


def test_assess_blocks_when_daily_loss_limit_already_breached() -> None:
    approval_request_id = _submit_one_setup()
    setup = setup_submission_service.get_approval(approval_request_id)

    # Simulate the account already having lost more than its daily limit today.
    # The account registry itself detects this and marks the account breached
    # -- even before the risk pipeline runs, which is the stronger, earlier
    # fail-closed gate. The pipeline's own active-status check then refuses.
    account_registry_service.update_state(
        setup.account_id,
        AccountStateUpdate(balance=94000.0, equity=94000.0),
    )
    assert account_registry_service.get_account(setup.account_id).status == AccountStatus.breached

    with pytest.raises(TradeRiskPipelineError, match="not active"):
        trade_risk_pipeline_service.assess(approval_request_id)


# -- open_position: the second real link ------------------------------------


def test_open_position_requires_a_risk_approved_record() -> None:
    approval_request_id = _submit_one_setup()
    setup = setup_submission_service.get_approval(approval_request_id)
    record = trade_risk_pipeline_service.assess(approval_request_id, RiskAssessmentRequest(value_per_price_unit=10.0))

    # A freshly-assessed A-grade setup on a healthy account should come back
    # risk-approved; if it didn't, the rest of this test would be moot.
    assert record.state == RiskState.RISK_APPROVED

    position = trade_risk_pipeline_service.open_position(str(setup.account_id), record.id)

    assert position.symbol == setup.symbol
    assert position.position_size == pytest.approx(record.assessment.recommended_position_units)
    assert position.risk_amount == pytest.approx(record.assessment.recommended_risk_amount)
    assert position.entry_price == setup.entry_price
    assert position.current_stop_price == setup.stop_loss
    assert position.state in (PositionState.PLANNED, PositionState.APPROVED, PositionState.HUMAN_REVIEW_REQUIRED)


def test_open_position_converts_cumulative_take_profits_to_incremental_exit_rules() -> None:
    """setup_submission's TakeProfit.close_pct is cumulative (e.g. 30/50/100);
    position_management_brain's ExitRule.close_percent is incremental and must
    not sum past 100. This must be converted, not passed through as-is."""
    from app.strategies.models import TakeProfit
    from app.trade_risk_pipeline.service import _exit_rules_from_take_profits

    take_profits = [
        TakeProfit(price=1.1010, close_pct=30, label="TP1"),
        TakeProfit(price=1.1020, close_pct=50, label="TP2"),
        TakeProfit(price=1.1030, close_pct=100, label="TP3"),
    ]
    rules = _exit_rules_from_take_profits(take_profits, "scalping_3tp")

    assert [round(r.close_percent, 6) for r in rules] == [30, 20, 50]
    assert sum(r.close_percent for r in rules) == pytest.approx(100)
    assert all(r.kind == "take-profit" for r in rules)
    assert [r.trigger_price for r in rules] == [1.1010, 1.1020, 1.1030]


def test_open_position_refuses_a_record_that_is_not_risk_approved() -> None:
    """Directly constructs a non-approved dynamic_risk_engine record (via its
    own API, not our heuristics) so this test doesn't depend on which inputs
    happen to trigger a block -- it only tests open_position's own guard."""
    approval_request_id = _submit_one_setup()
    setup = setup_submission_service.get_approval(approval_request_id)

    from app.modules.dynamic_risk_engine.models import AccountRiskSnapshot, DynamicRiskCreate
    from app.modules.dynamic_risk_engine.router import service as dynamic_risk_service

    not_approved_record = dynamic_risk_service.create(
        DynamicRiskCreate(
            workspace_id=str(setup.account_id),
            source_key=str(setup.approval_request_id),
            position_management_record_id=str(setup.approval_request_id),
            v21_16_approved=False,  # deterministically yields EVIDENCE_REQUIRED, never risk-approved
            symbol=setup.symbol,
            direction="long" if setup.side.value == "buy" else "short",
            setup_grade="B",
            setup_confidence_score=setup.confidence,
            entry_price=setup.entry_price,
            stop_price=setup.stop_loss,
            value_per_price_unit=10.0,
            account=AccountRiskSnapshot(balance=100000, equity=100000, daily_start_equity=100000, initial_account_size=100000),
        )
    )
    assert not_approved_record.state != RiskState.RISK_APPROVED

    with pytest.raises(TradeRiskPipelineError, match="not risk-approved"):
        trade_risk_pipeline_service.open_position(str(setup.account_id), not_approved_record.id)


def test_open_position_unknown_risk_record_fails_closed() -> None:
    approval_request_id = _submit_one_setup()
    setup = setup_submission_service.get_approval(approval_request_id)
    with pytest.raises(TradeRiskPipelineError, match="record not found"):
        trade_risk_pipeline_service.open_position(str(setup.account_id), "does-not-exist")


# -- start_supervision: the third real link ----------------------------------


def _open_a_position() -> tuple[str, str]:
    """Runs the full assess -> open_position chain and returns (workspace_id, position_id)."""
    approval_request_id = _submit_one_setup()
    setup = setup_submission_service.get_approval(approval_request_id)
    record = trade_risk_pipeline_service.assess(approval_request_id, RiskAssessmentRequest(value_per_price_unit=10.0))
    assert record.state == RiskState.RISK_APPROVED
    position = trade_risk_pipeline_service.open_position(str(setup.account_id), record.id)
    return str(setup.account_id), position.id


def test_start_supervision_on_a_freshly_opened_position() -> None:
    workspace_id, position_id = _open_a_position()
    record = trade_risk_pipeline_service.start_supervision(workspace_id, position_id)

    assert record.workflow_id == position_id
    assert record.total_stages == 1
    assert record.stage_snapshots[0].stage_key == "position-lifecycle"
    assert record.state != SupervisionState.EVIDENCE_REQUIRED
    assert record.state != SupervisionState.BLOCKED


def test_start_supervision_unknown_position_fails_closed() -> None:
    with pytest.raises(TradeRiskPipelineError, match="record not found"):
        trade_risk_pipeline_service.start_supervision("some-workspace", "does-not-exist")


def test_start_supervision_refuses_a_closed_position() -> None:
    workspace_id, position_id = _open_a_position()

    from app.modules.position_management_brain.models import PositionAction, PositionCommand
    from app.modules.position_management_brain.router import service as position_management_service

    # Drive the position through its real lifecycle (approve -> mark-open ->
    # close) using its own commands, then confirm supervision refuses a
    # closed position.
    position_management_service.execute(
        workspace_id, position_id, PositionAction(command=PositionCommand.APPROVE, actor="test")
    )
    position_management_service.execute(
        workspace_id,
        position_id,
        PositionAction(command=PositionCommand.MARK_OPEN, actor="test", downstream_receipt="receipt-1"),
    )
    position_management_service.execute(
        workspace_id, position_id, PositionAction(command=PositionCommand.CLOSE, actor="test", realized_r_multiple=1.5)
    )

    with pytest.raises(TradeRiskPipelineError, match="not in a supervisable state"):
        trade_risk_pipeline_service.start_supervision(workspace_id, position_id)


def test_start_supervision_cannot_be_started_twice_for_the_same_position() -> None:
    workspace_id, position_id = _open_a_position()
    trade_risk_pipeline_service.start_supervision(workspace_id, position_id)

    with pytest.raises(TradeRiskPipelineError, match="duplicate source_key"):
        trade_risk_pipeline_service.start_supervision(workspace_id, position_id)
