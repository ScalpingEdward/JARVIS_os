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
