from __future__ import annotations

from uuid import UUID

from .models import (
    ApprovalRequest,
    AuditRecord,
    OrderIntent,
    OrderIntentCreate,
    OrderRoutingState,
    OrderRoutingStatusResponse,
)


class ExecutiveOrderRoutingService:
    def __init__(self) -> None:
        self._records: dict[UUID, OrderIntent] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._intent_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def reset(self) -> None:
        self._records.clear()
        self._source_keys.clear()
        self._intent_ids.clear()
        self._audit.clear()

    def assess(self, payload: OrderIntentCreate) -> OrderIntent:
        source_key = (payload.workspace_id, payload.source_key)
        intent_key = (payload.workspace_id, payload.intent_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate order-routing source key")
        if intent_key in self._intent_ids:
            raise ValueError("Duplicate order intent ID")

        state, reasons, action = self._evaluate(payload)
        record = OrderIntent(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            intent_id=payload.intent_id,
            broker_session_id=payload.broker_session_id,
            market_data_subscription_id=payload.market_data_subscription_id,
            account_reference=payload.account_reference,
            canonical_symbol=payload.canonical_symbol,
            side=payload.side,
            order_type=payload.order_type,
            time_in_force=payload.time_in_force,
            volume=payload.volume,
            requested_price=payload.requested_price,
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit,
            max_slippage_points=payload.max_slippage_points,
            strategy_id=payload.strategy_id,
            state=state,
            pretrade_approved=state in {OrderRoutingState.pretrade_approved, OrderRoutingState.ready_for_dispatch},
            dispatch_allowed=state == OrderRoutingState.ready_for_dispatch,
            recommended_action=action,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._intent_ids.add(intent_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, intent_id=record.intent_id, actor_id=payload.actor_id, action="order-intent-assessed"))
        return record

    def _evaluate(self, payload: OrderIntentCreate) -> tuple[OrderRoutingState, list[str], str]:
        o, p = payload.observation, payload.policy
        if not payload.risk_brain_clear:
            return OrderRoutingState.blocked, ["Risk Brain blocked order intent"], "keep-order-blocked"
        if p.require_policy_authorization and o.policy_state != "ready-for-dispatch":
            return OrderRoutingState.blocked, ["Policy Engine did not authorize dispatch"], "resolve-policy-decision"
        if p.require_market_data and o.market_data_state != "stream-ready":
            return OrderRoutingState.market_data_required, ["Validated market-data stream is required"], "restore-market-data"
        if p.require_broker_session and o.broker_session_state != "session-ready":
            return OrderRoutingState.broker_session_required, ["Ready broker session is required"], "restore-broker-session"
        if o.duplicate_intent:
            return OrderRoutingState.invalid_order, ["Duplicate order intent detected"], "discard-duplicate-intent"
        if p.require_registered_symbol and not o.symbol_registered:
            return OrderRoutingState.invalid_order, ["Canonical symbol is not registered"], "resolve-symbol"
        if p.require_market_open and not o.market_open:
            return OrderRoutingState.route_unavailable, ["Market is closed"], "wait-for-market-open"
        if not o.route_available:
            return OrderRoutingState.route_unavailable, ["No eligible execution route is available"], "select-failover-route"
        if p.require_trade_enabled and not o.account_trade_enabled:
            return OrderRoutingState.risk_rejected, ["Trading is disabled for account"], "enable-account-trading"
        risk_checks = [
            (not p.require_margin or o.margin_sufficient, "Insufficient margin"),
            (not p.enforce_exposure_limits or o.exposure_within_limits, "Exposure limit exceeded"),
            (not p.enforce_daily_loss_limit or o.daily_loss_within_limits, "Daily loss limit exceeded"),
            (not p.enforce_max_drawdown or o.max_drawdown_within_limits, "Maximum drawdown limit exceeded"),
            (not p.enforce_spread_limit or o.spread_within_limit, "Spread limit exceeded"),
            (not p.enforce_slippage_limit or o.slippage_within_limit, "Slippage limit exceeded"),
        ]
        failures = [message for passed, message in risk_checks if not passed]
        if failures:
            return OrderRoutingState.risk_rejected, failures, "reject-order-intent"
        validation_checks = [
            (o.volume_valid, "Order volume is invalid"),
            (o.price_valid, "Order price is invalid"),
            (not p.require_stop_loss or o.stop_loss_valid, "Stop loss is invalid or missing"),
            (not p.require_take_profit or o.take_profit_valid, "Take profit is invalid or missing"),
        ]
        validation_failures = [message for passed, message in validation_checks if not passed]
        if validation_failures:
            return OrderRoutingState.invalid_order, validation_failures, "correct-order-intent"
        if p.require_human_approval and not o.human_approval_present:
            return OrderRoutingState.approval_required, ["Explicit human approval is required"], "request-human-approval"
        return OrderRoutingState.ready_for_dispatch, ["Order intent passed pre-trade governance"], "dispatch-through-single-adapter"

    def approve(self, request: ApprovalRequest) -> OrderIntent:
        record = next((r for r in self._records.values() if r.workspace_id == request.workspace_id and r.intent_id == request.intent_id), None)
        if record is None:
            raise KeyError("Order intent not found")
        if not request.approved:
            record.state = OrderRoutingState.blocked
            record.pretrade_approved = False
            record.dispatch_allowed = False
            record.recommended_action = "keep-order-blocked"
            record.reasons = ["Human approval was denied"]
            action = "order-intent-denied"
        elif record.state != OrderRoutingState.approval_required:
            raise ValueError("Order intent is not awaiting approval")
        else:
            record.state = OrderRoutingState.ready_for_dispatch
            record.pretrade_approved = True
            record.dispatch_allowed = True
            record.recommended_action = "dispatch-through-single-adapter"
            record.reasons = ["Explicit human approval recorded"]
            action = "order-intent-approved"
        self._audit.append(AuditRecord(workspace_id=request.workspace_id, assessment_id=record.id, intent_id=record.intent_id, actor_id=request.actor_id, action=action))
        return record

    def list_intents(self, workspace_id: str) -> list[OrderIntent]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> OrderIntent | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> OrderRoutingStatusResponse:
        records = self.list_intents(workspace_id)
        ready = sum(r.dispatch_allowed for r in records)
        return OrderRoutingStatusResponse(workspace_id=workspace_id, intents=len(records), ready_for_dispatch=ready, blocked_or_rejected=len(records) - ready, latest_state=records[-1].state if records else None)

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [r for r in self._audit if r.workspace_id == workspace_id]


executive_order_routing_service = ExecutiveOrderRoutingService()
