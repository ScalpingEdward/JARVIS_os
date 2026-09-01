from __future__ import annotations

from uuid import UUID

from app.accounts.models import AccountStatus, TradingAccountRecord
from app.accounts.service import account_registry_service
from app.modules.dynamic_risk_engine.models import (
    AccountRiskSnapshot,
    DynamicRiskCreate,
    DynamicRiskRecord,
    RiskPolicy,
    RiskState,
)
from app.modules.dynamic_risk_engine.router import service as dynamic_risk_service
from app.modules.dynamic_risk_engine.service import DynamicRiskError
from app.modules.execution_supervisor.models import StageTelemetry, SupervisionCreate, SupervisionRecord
from app.modules.execution_supervisor.router import service as execution_supervisor_service
from app.modules.execution_supervisor.service import ExecutionSupervisorError
from app.modules.position_management_brain.models import ExitRule, PositionCreate, PositionRecord, PositionState
from app.modules.position_management_brain.router import service as position_management_service
from app.modules.position_management_brain.service import PositionManagementError
from app.setup_submission.models import SubmittedSetup, TradeSide
from app.setup_submission.service import setup_submission_service

from .models import RiskAssessmentRequest, SupervisionStartRequest

_SUPERVISABLE_POSITION_STATES = {
    PositionState.PLANNED,
    PositionState.APPROVED,
    PositionState.OPEN,
    PositionState.PROTECTED,
    PositionState.SCALING_OUT,
}


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


def _exit_rules_from_take_profits(take_profits: list, strategy_id: str) -> list[ExitRule]:
    """Converts setup_submission's *cumulative* TakeProfit.close_pct (e.g.
    30/50/100) into position_management_brain's *incremental* ExitRule.close_percent,
    which must not sum past 100. Pulled out as its own function so the
    conversion itself is directly testable without touching either service's
    internal state."""
    rules: list[ExitRule] = []
    previous_cumulative = 0.0
    for index, tp in enumerate(take_profits, start=1):
        incremental = max(0.0, tp.close_pct - previous_cumulative)
        previous_cumulative = tp.close_pct
        rules.append(
            ExitRule(
                key=f"strategy-tp-{index}",
                kind="take-profit",
                trigger_price=tp.price,
                close_percent=incremental,
                evidence_ref=f"strategy:{strategy_id}",
            )
        )
    return rules


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

    def _get_risk_record(self, workspace_id: str, risk_record_id: str) -> DynamicRiskRecord:
        try:
            return dynamic_risk_service.get(workspace_id, risk_record_id)
        except DynamicRiskError as exc:
            raise TradeRiskPipelineError(str(exc)) from exc

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

    def open_position(self, workspace_id: str, risk_record_id: str) -> PositionRecord:
        """Opens a tracked position from an already risk-approved assessment.

        This is the second real link: dynamic_risk_engine already computed a
        governed position size (assess() above); this takes that approved
        record and opens the position in position_management_brain with the
        strategy's own take-profits mapped to real exit rules, so partial
        closes / break-even / trailing-stop management has something real to
        act on later instead of a setup that was only ever "approved" on
        paper. Still does not place a broker order.
        """
        risk_record = self._get_risk_record(workspace_id, risk_record_id)
        if risk_record.state != RiskState.RISK_APPROVED:
            raise TradeRiskPipelineError(
                f"Risk record {risk_record_id} is {risk_record.state}, not risk-approved; refusing to open a position"
            )

        account = account_registry_service.get_account(UUID(workspace_id))
        if account.status != AccountStatus.active:
            raise TradeRiskPipelineError(
                f"Account {account.id} is {account.status}, not active; refusing to open a position for it"
            )

        approval_request_id = UUID(risk_record.source_key)
        setup = setup_submission_service.get_approval(approval_request_id)
        if setup is None:
            raise TradeRiskPipelineError(f"No setup found for risk record {risk_record_id} (source_key {risk_record.source_key})")

        # Strategy take-profits express *cumulative* close percentage;
        # position_management_brain's exit rules need incremental values.
        exit_rules = _exit_rules_from_take_profits(setup.take_profits, setup.strategy_id)

        payload = PositionCreate(
            workspace_id=workspace_id,
            source_key=str(approval_request_id),
            trade_setup_record_id=str(approval_request_id),
            v21_15_approved=True,
            v21_15_evidence={
                "risk_record_id": risk_record_id,
                "risk_state": risk_record.state.value,
                "source": "trade_risk_pipeline",
            },
            symbol=setup.symbol,
            direction="long" if setup.side == TradeSide.buy else "short",
            entry_price=setup.entry_price,
            initial_stop_price=setup.stop_loss,
            position_size=risk_record.assessment.recommended_position_units,
            risk_amount=risk_record.assessment.recommended_risk_amount,
            exit_rules=exit_rules,
        )
        return position_management_service.create(payload, actor="trade_risk_pipeline")

    def start_supervision(
        self, workspace_id: str, position_id: str, request: SupervisionStartRequest | None = None
    ) -> SupervisionRecord:
        """Starts execution_supervisor tracking for an already-opened position.

        The third real link: dynamic_risk_engine sized it, position_management_brain
        opened it, this puts it under ongoing health supervision (stale-heartbeat,
        error-rate, quality-score monitoring) so degradation gets flagged instead
        of a position silently going unmonitored after it's opened.
        """
        request = request or SupervisionStartRequest()

        try:
            position = position_management_service.get(workspace_id, position_id)
        except PositionManagementError as exc:
            raise TradeRiskPipelineError(str(exc)) from exc

        if position.state not in _SUPERVISABLE_POSITION_STATES:
            raise TradeRiskPipelineError(
                f"Position {position_id} is {position.state}, not in a supervisable state "
                f"({sorted(s.value for s in _SUPERVISABLE_POSITION_STATES)}); refusing to start supervision"
            )

        stage = StageTelemetry(
            stage_key="position-lifecycle",
            status=position.state.value,
            progress_percent=max(0.0, 100.0 - position.remaining_percent),
            elapsed_seconds=0,
            timeout_seconds=request.timeout_seconds,
            dependency_healthy=True,
            metadata={"symbol": position.symbol, "direction": position.direction},
        )
        payload = SupervisionCreate(
            workspace_id=workspace_id,
            source_key=position_id,
            workflow_id=position_id,
            workflow_approved=True,
            v21_10_evidence={"source": "trade_risk_pipeline", "position_id": position_id},
            stale_heartbeat_seconds=request.stale_heartbeat_seconds,
            minimum_quality_score=request.minimum_quality_score,
            maximum_error_rate=request.maximum_error_rate,
            stages=[stage],
        )
        try:
            return execution_supervisor_service.create(payload, actor="trade_risk_pipeline")
        except ExecutionSupervisorError as exc:
            raise TradeRiskPipelineError(str(exc)) from exc


trade_risk_pipeline_service = TradeRiskPipelineService()
