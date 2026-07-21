from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    CanaryResultRequest,
    ControlledReentryAssessment,
    ControlledReentryAssessmentCreate,
    ControlledReentryState,
    ControlledReentryStatusResponse,
    FullReenableRequest,
)


class ExecutiveControlledReentryService:
    def __init__(self) -> None:
        self._records: dict[UUID, ControlledReentryAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._reentry_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def reset(self) -> None:
        self._records.clear()
        self._source_keys.clear()
        self._reentry_ids.clear()
        self._audit.clear()

    def assess(self, payload: ControlledReentryAssessmentCreate) -> ControlledReentryAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        reentry_key = (payload.workspace_id, payload.reentry_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate controlled re-entry source key")
        if reentry_key in self._reentry_ids:
            raise ValueError("Duplicate re-entry ID")

        state, reasons, action = self._evaluate(payload)
        o = payload.observation
        record = ControlledReentryAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            reentry_id=payload.reentry_id,
            containment_id=payload.containment_id,
            account_reference=payload.account_reference,
            broker_reference=payload.broker_reference,
            state=state,
            canary_risk_pct=o.canary_risk_pct,
            canary_orders=o.canary_orders,
            canary_failures=o.canary_failures,
            new_orders_enabled=state in {ControlledReentryState.limited_trading, ControlledReentryState.trading_reenabled},
            full_trading_enabled=state == ControlledReentryState.trading_reenabled,
            recommended_action=action,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._reentry_ids.add(reentry_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, record_id=record.id, reentry_id=record.reentry_id, actor_id=payload.actor_id, action="controlled-reentry-assessed"))
        return record

    def _evaluate(self, payload: ControlledReentryAssessmentCreate) -> tuple[ControlledReentryState, list[str], str]:
        o, p = payload.observation, payload.policy
        if not payload.risk_brain_clear:
            return ControlledReentryState.blocked, ["Risk Brain blocked controlled re-entry"], "keep-trading-blocked"
        if p.require_released_containment and o.containment_state != "released":
            return ControlledReentryState.containment_release_required, ["Emergency containment must be released first"], "complete-containment-release"
        if p.require_account_risk_clear and o.account_risk_state != "account-risk-clear":
            return ControlledReentryState.account_reconciliation_required, ["Account risk is not clear"], "reconcile-account-risk"
        broker_ready = o.broker_session_ready and o.market_data_ready and o.positions_reconciled and o.pending_orders_reconciled
        if p.require_broker_reconciliation and not broker_ready:
            return ControlledReentryState.account_reconciliation_required, ["Broker, market data, positions or orders are not reconciled"], "reconcile-runtime-state"
        incident_ready = o.incident_review_completed and o.root_cause_identified and o.remediation_verified
        if p.require_incident_review and not incident_ready:
            return ControlledReentryState.readiness_required, ["Incident review, root cause or remediation verification is incomplete"], "complete-incident-remediation"
        if o.cooldown_elapsed_minutes < p.minimum_cooldown_minutes:
            return ControlledReentryState.cooldown_active, ["Mandatory recovery cooldown is still active"], "wait-for-cooldown"
        if p.require_human_approval and not o.human_approval_verified:
            return ControlledReentryState.approval_required, ["Explicit human approval is required before canary trading"], "request-canary-approval"
        if p.require_canary:
            if not o.canary_requested or not o.canary_dispatched or not o.canary_acknowledged:
                return ControlledReentryState.canary_required, ["A governed canary trade is required"], "dispatch-approved-canary"
            canary_failed = (
                o.canary_risk_pct > p.maximum_canary_risk_pct
                or o.canary_orders > p.maximum_canary_orders
                or o.canary_failures > p.maximum_canary_failures
                or o.canary_slippage_bps > p.maximum_canary_slippage_bps
                or (p.require_canary_reconciliation and not o.canary_reconciliation_complete)
            )
            if canary_failed:
                return ControlledReentryState.canary_failed, ["Canary risk, failures, slippage or reconciliation breached policy"], "recontain-and-investigate"
        if o.full_reenable_requested:
            if p.require_human_approval_for_full_reenable and not o.full_reenable_human_approved:
                return ControlledReentryState.approval_required, ["Explicit human approval is required for full trading re-enable"], "request-full-reenable-approval"
            return ControlledReentryState.trading_reenabled, ["Controlled recovery and full trading re-enable completed"], "resume-governed-trading"
        return ControlledReentryState.limited_trading, ["Canary passed; trading remains limited"], "monitor-limited-trading"

    def list_assessments(self, workspace_id: str) -> list[ControlledReentryAssessment]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> ControlledReentryAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def record_canary(self, request: CanaryResultRequest) -> ControlledReentryAssessment:
        record = next((r for r in self._records.values() if r.workspace_id == request.workspace_id and r.reentry_id == request.reentry_id), None)
        if record is None:
            raise KeyError("Controlled re-entry record not found")
        if not request.human_approval_verified:
            raise ValueError("Explicit human approval is required")
        failed = (
            not request.canary_dispatched
            or not request.canary_acknowledged
            or request.canary_orders > 3
            or request.canary_failures > 0
            or request.canary_slippage_bps > 30
            or not request.reconciliation_complete
        )
        record.canary_orders = request.canary_orders
        record.canary_failures = request.canary_failures
        if failed:
            record.state = ControlledReentryState.canary_failed
            record.new_orders_enabled = False
            record.full_trading_enabled = False
            record.recommended_action = "recontain-and-investigate"
            record.reasons = ["Canary result failed controlled re-entry policy"]
        else:
            record.state = ControlledReentryState.limited_trading
            record.new_orders_enabled = True
            record.full_trading_enabled = False
            record.recommended_action = "monitor-limited-trading"
            record.reasons = ["Canary completed successfully; limited trading enabled"]
        self._audit.append(AuditRecord(workspace_id=request.workspace_id, record_id=record.id, reentry_id=record.reentry_id, actor_id=request.actor_id, action="controlled-reentry-canary-recorded"))
        return record

    def full_reenable(self, request: FullReenableRequest) -> ControlledReentryAssessment:
        record = next((r for r in self._records.values() if r.workspace_id == request.workspace_id and r.reentry_id == request.reentry_id), None)
        if record is None:
            raise KeyError("Controlled re-entry record not found")
        if record.state != ControlledReentryState.limited_trading:
            raise ValueError("Successful limited-trading state is required")
        if not request.human_approval_verified:
            raise ValueError("Explicit human approval is required")
        if request.account_risk_state != "account-risk-clear" or not request.broker_session_ready or not request.market_data_ready:
            raise ValueError("Account risk, broker session and market data must remain clear")
        record.state = ControlledReentryState.trading_reenabled
        record.new_orders_enabled = True
        record.full_trading_enabled = True
        record.recommended_action = "resume-governed-trading"
        record.reasons = ["Full governed trading re-enable approved"]
        self._audit.append(AuditRecord(workspace_id=request.workspace_id, record_id=record.id, reentry_id=record.reentry_id, actor_id=request.actor_id, action="controlled-reentry-fully-enabled"))
        return record

    def status(self, workspace_id: str) -> ControlledReentryStatusResponse:
        records = self.list_assessments(workspace_id)
        limited = sum(r.state == ControlledReentryState.limited_trading for r in records)
        fully_reenabled = sum(r.state == ControlledReentryState.trading_reenabled for r in records)
        return ControlledReentryStatusResponse(
            workspace_id=workspace_id,
            assessments=len(records),
            blocked_or_waiting=len(records) - limited - fully_reenabled,
            limited=limited,
            fully_reenabled=fully_reenabled,
            latest_state=records[-1].state if records else None,
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [r for r in self._audit if r.workspace_id == workspace_id]


executive_controlled_reentry_service = ExecutiveControlledReentryService()
