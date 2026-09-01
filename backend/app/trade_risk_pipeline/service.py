from __future__ import annotations

from uuid import UUID

from app.accounts.models import AccountStatus, TradingAccountRecord
from app.accounts.service import account_registry_service
from app.modules.dynamic_risk_engine.models import (
    AccountRiskSnapshot,
    DynamicRiskCreate,
    DynamicRiskRecord,
    RiskPolicy,
)
from app.modules.dynamic_risk_engine.router import service as dynamic_risk_service
from app.setup_submission.models import SubmittedSetup, TradeSide
from app.setup_submission.service import setup_submission_service

from .models import RiskAssessmentRequest


class TradeRiskPipelineError(ValueError):
    pass


def _setup_grade(confidence: float) -> str:
    """Coarse grade the dynamic risk engine's schema requires. Derived
    directly from the strategy's own confidence score -- not a second
    opinion, just the shape dynamic_risk_engine's contract expects."""
    if confidence >= 85:
        return "A+"
    if confidence >= 70:
        return "A"
    if confidence >= 55:
        return "B"
    return "C"


def _account_snapshot(account: TradingAccountRecord) -> AccountRiskSnapshot:
    return AccountRiskSnapshot(
        balance=account.balance,
        equity=account.equity,
        daily_start_equity=account.day_start_balance,
        initial_account_size=account.initial_balance,
        realized_daily_pnl=account.equity - account.day_start_balance,
    )


def _policy_from_account(account: TradingAccountRecord, base_risk_percent: float | None) -> RiskPolicy:
    rules = account.prop_rules
    kwargs: dict[str, float] = {}
    if rules is not None:
        kwargs["maximum_daily_loss_percent"] = rules.max_daily_loss_pct
        kwargs["maximum_total_drawdown_percent"] = rules.max_total_drawdown_pct
    if base_risk_percent is not None:
        kwargs["base_risk_percent"] = base_risk_percent
        kwargs.setdefault("maximum_risk_percent", max(base_risk_percent, 1.0))
    return RiskPolicy(**kwargs)


class TradeRiskPipelineService:
    """The real link between an approved setup and a governed position size.

    setup_submission already gates *which* setups reach a human for
    approval. This is the next real link in the chain: once approved, it
    pulls the account's live balance/equity/prop-firm rules and runs them
    through dynamic_risk_engine to get an actual, policy-bounded position
    size -- rather than leaving position sizing as manual judgment, which
    is the exact failure mode flagged repeatedly in past trading review
    (oversized entries, conviction-based sizing instead of stop-distance-
    and-risk-percent-based sizing).

    This does not open a position or place an order. It produces a
    DynamicRiskRecord (risk-approved, human-review-required, or blocked)
    that a later, still-gated step would need before any execution.
    """

    def assess(self, approval_request_id: UUID, request: RiskAssessmentRequest | None = None) -> DynamicRiskRecord:
        request = request or RiskAssessmentRequest()

        setup = setup_submission_service.get_approval(approval_request_id)
        if setup is None:
            raise TradeRiskPipelineError(f"No pending/approved setup found for {approval_request_id}")

        account = account_registry_service.get_account(setup.account_id)
        if account.status != AccountStatus.active:
            raise TradeRiskPipelineError(
                f"Account {account.id} is {account.status}, not active; refusing to size a position for it"
            )

        payload = DynamicRiskCreate(
            workspace_id=str(account.id),
            source_key=str(setup.approval_request_id),
            position_management_record_id=str(setup.approval_request_id),
            v21_16_approved=True,
            v21_16_evidence={
                "source": "trade_risk_pipeline",
                "strategy_id": setup.strategy_id,
                "reasoning": setup.reasoning,
                "risk_reward": setup.risk_reward,
            },
            symbol=setup.symbol,
            direction="long" if setup.side == TradeSide.buy else "short",
            setup_grade=_setup_grade(setup.confidence),
            setup_confidence_score=setup.confidence,
            entry_price=setup.entry_price,
            stop_price=setup.stop_loss,
            value_per_price_unit=request.value_per_price_unit,
            account=_account_snapshot(account),
            policy=_policy_from_account(account, request.base_risk_percent),
        )
        return dynamic_risk_service.create(payload, actor="trade_risk_pipeline")


trade_risk_pipeline_service = TradeRiskPipelineService()
