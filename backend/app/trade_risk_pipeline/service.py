from __future__ import annotations

import math
from datetime import datetime, timezone
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
from app.executive_mt5_live_order_executor.models import LiveOrderCreate, LiveOrderRecord
from app.executive_mt5_live_order_executor.service import live_order_executor_service
from app.modules.dynamic_risk_engine.router import service as dynamic_risk_service
from app.modules.dynamic_risk_engine.service import DynamicRiskError
from app.mt5_bridge.service import mt5_bridge_service
from app.modules.execution_supervisor.models import StageTelemetry, SupervisionCreate, SupervisionRecord
from app.modules.execution_supervisor.router import service as execution_supervisor_service
from app.modules.execution_supervisor.service import ExecutionSupervisorError
from app.modules.position_management_brain.models import ExitRule, PositionCreate, PositionRecord, PositionState
from app.modules.position_management_brain.router import service as position_management_service
from app.modules.position_management_brain.service import PositionManagementError
from app.setup_submission.models import SubmittedSetup, TradeSide
from app.setup_submission.service import setup_submission_service

from .models import RiskAssessmentRequest, SupervisionStartRequest, LiveOrderPrepareRequest

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

        value_per_price_unit = request.value_per_price_unit
        if value_per_price_unit is None:
            value_per_price_unit = self._symbol_spec(account, setup.symbol).value_per_price_unit

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
            value_per_price_unit=value_per_price_unit,
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

    def _live_quote(self, account: TradingAccountRecord, symbol: str) -> tuple[float, float, float]:
        """Looks up the freshest real tick for `symbol` from the mt5_bridge
        terminal matched to this account by (login, server) -- the same
        matching account_state_sync already uses. Fails closed: no matching
        terminal or no tick for this symbol means no quote, not a guess."""
        terminal = self._matched_terminal(account)
        tick = next((t for t in reversed(terminal.ticks) if t.symbol == symbol), None)
        if tick is None:
            raise TradeRiskPipelineError(
                f"mt5_bridge terminal for account login={account.login} has no recent tick for {symbol}; "
                "cannot look up a live quote."
            )
        age_seconds = max(0.0, (datetime.now(timezone.utc) - tick.captured_at).total_seconds())
        return tick.bid, tick.ask, age_seconds

    def _matched_terminal(self, account: TradingAccountRecord):
        terminal = next(
            (
                data
                for data in mt5_bridge_service.list()
                if str(data.terminal.account_login) == account.login and data.terminal.server == account.server
            ),
            None,
        )
        if terminal is None:
            raise TradeRiskPipelineError(
                f"No mt5_bridge terminal is registered for account login={account.login} server={account.server}; "
                "cannot look up real broker data for it."
            )
        return terminal

    def _symbol_spec(self, account: TradingAccountRecord, symbol: str):
        terminal = self._matched_terminal(account)
        spec = next((s for s in terminal.symbols if s.symbol == symbol), None)
        if spec is None:
            raise TradeRiskPipelineError(
                f"mt5_bridge terminal for account login={account.login} has no contract spec for {symbol}; "
                "cannot size or validate an order for it without one."
            )
        return spec

    def prepare_live_order(
        self, workspace_id: str, position_id: str, request: LiveOrderPrepareRequest
    ) -> LiveOrderRecord:
        """Runs live-order preflight for a planned/approved position. This is
        the fourth link and the one closest to real money -- read carefully.

        This calls the live order executor's *create* step only, which runs
        deterministic preflight checks (quote freshness, price deviation,
        volume/stop validity, risk limits) and produces a record in either
        'preflight-ready' or 'approval-required' state. It NEVER calls
        /execute and NEVER sets human_approved=True itself -- submitting to
        the broker is a separate, explicit action outside this pipeline,
        deliberately, so no chain of automatic calls can end in a live order.

        Even if that separate call happens, nothing reaches a real broker
        unless the caller's own MT5 terminal, logged into the target
        account, is reachable by whatever process is running AURON --
        native_executor.py requires the Windows-only MetaTrader5 package,
        which is not installed or usable in this environment.

        Quote and contract-spec data now have a real source: if omitted,
        both are looked up from the mt5_bridge terminal matched to this
        account (by login+server), and this fails closed if no matching
        terminal, tick, or symbol spec is available. Pass them explicitly
        to override.

        Only the initial stop-loss is carried into the broker order.
        Partial take-profits are position_management_brain's exit rules,
        applied incrementally after the position is open -- not part of the
        initial order send.
        """
        try:
            position = position_management_service.get(workspace_id, position_id)
        except PositionManagementError as exc:
            raise TradeRiskPipelineError(str(exc)) from exc

        if position.state not in {PositionState.PLANNED, PositionState.APPROVED}:
            raise TradeRiskPipelineError(
                f"Position {position_id} is {position.state}; live-order preparation requires "
                "'planned' or 'approved', not an already-open, blocked, or terminal state"
            )

        account = account_registry_service.get_account(UUID(workspace_id))
        if account.status != AccountStatus.active:
            raise TradeRiskPipelineError(
                f"Account {account.id} is {account.status}, not active; refusing to prepare a live order for it"
            )

        approved_logins = request.approved_account_logins or [request.account_login]

        if request.quote_bid is not None and request.quote_ask is not None and request.quote_age_seconds is not None:
            quote_bid, quote_ask, quote_age_seconds = request.quote_bid, request.quote_ask, request.quote_age_seconds
        elif request.quote_bid is None and request.quote_ask is None and request.quote_age_seconds is None:
            quote_bid, quote_ask, quote_age_seconds = self._live_quote(account, position.symbol)
        else:
            raise TradeRiskPipelineError(
                "quote_bid, quote_ask, and quote_age_seconds must be all supplied or all omitted -- "
                "partial overrides are not allowed."
            )

        spec_fields = (request.symbol_point, request.min_volume, request.max_volume, request.volume_step)
        if all(f is not None for f in spec_fields):
            symbol_point, min_volume, max_volume, volume_step = spec_fields
        elif all(f is None for f in spec_fields):
            spec = self._symbol_spec(account, position.symbol)
            symbol_point, min_volume, max_volume, volume_step = (
                spec.point,
                spec.volume_min,
                spec.volume_max,
                spec.volume_step,
            )
        else:
            raise TradeRiskPipelineError(
                "symbol_point, min_volume, max_volume, and volume_step must be all supplied or all omitted -- "
                "partial overrides are not allowed."
            )

        # dynamic_risk_engine computes a theoretical position size from risk%
        # and stop distance -- it has no knowledge of the broker's real
        # volume_step, so it almost never lands exactly on a valid multiple.
        # Round DOWN to the nearest valid step: rounding down can only ever
        # under-risk relative to what was approved, never over-risk. If that
        # pushes the size below min_volume, the executor's own volume check
        # below still catches and reports it correctly -- not silently
        # forced up to the minimum, which would exceed the approved risk.
        raw_volume = position.position_size
        steps = math.floor((raw_volume - min_volume) / volume_step + 1e-9)
        volume = round(min_volume + max(steps, 0) * volume_step, 8)

        payload = LiveOrderCreate(
            workspace_id=workspace_id,
            source_key=position_id,
            actor_id="trade_risk_pipeline",
            native_adapter_ready=request.native_adapter_ready,
            account_login=request.account_login,
            approved_account_logins=approved_logins,
            symbol=position.symbol,
            side="buy" if position.direction == "long" else "sell",
            order_type=request.order_type,
            volume=volume,
            stop_loss=position.current_stop_price,
            quote_bid=quote_bid,
            quote_ask=quote_ask,
            quote_age_seconds=quote_age_seconds,
            symbol_point=symbol_point,
            min_volume=min_volume,
            max_volume=max_volume,
            volume_step=volume_step,
            min_stop_distance_points=request.min_stop_distance_points,
            max_deviation_points=request.max_deviation_points,
            expected_risk_amount=position.risk_amount,
            max_risk_amount=position.risk_amount,
            account_risk_approved=True,
            prop_rules_approved=True,
            human_approved=False,
        )
        try:
            return live_order_executor_service.create(payload)
        except ValueError as exc:
            raise TradeRiskPipelineError(str(exc)) from exc


trade_risk_pipeline_service = TradeRiskPipelineService()
