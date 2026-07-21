from __future__ import annotations

from uuid import UUID

from .models import (
    AccountRiskAssessment,
    AccountRiskAssessmentCreate,
    AccountRiskState,
    AccountRiskStatusResponse,
    AuditRecord,
    RiskReductionRequest,
)


class ExecutiveAccountRiskService:
    def __init__(self) -> None:
        self._records: dict[UUID, AccountRiskAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._assessment_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def reset(self) -> None:
        self._records.clear()
        self._source_keys.clear()
        self._assessment_ids.clear()
        self._audit.clear()

    def assess(self, payload: AccountRiskAssessmentCreate) -> AccountRiskAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        assessment_key = (payload.workspace_id, payload.assessment_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate account-risk source key")
        if assessment_key in self._assessment_ids:
            raise ValueError("Duplicate account-risk assessment ID")

        state, reasons, action = self._evaluate(payload)
        o = payload.observation
        daily_loss_pct = max((o.start_of_day_balance - o.equity) / o.start_of_day_balance * 100, 0)
        drawdown_pct = max((o.initial_account_balance - o.equity) / o.initial_account_balance * 100, 0)
        margin_level_pct = None if o.used_margin == 0 else o.equity / o.used_margin * 100
        total_open_risk_pct = o.open_risk_pct + o.pending_order_risk_pct
        record = AccountRiskAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            assessment_id=payload.assessment_id,
            account_reference=payload.account_reference,
            broker_reference=payload.broker_reference,
            state=state,
            daily_loss_pct=round(daily_loss_pct, 6),
            drawdown_pct=round(drawdown_pct, 6),
            margin_level_pct=None if margin_level_pct is None else round(margin_level_pct, 6),
            total_open_risk_pct=round(total_open_risk_pct, 6),
            reduction_required=state not in {AccountRiskState.account_risk_clear},
            recommended_action=action,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._assessment_ids.add(assessment_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, record_id=record.id, assessment_id=record.assessment_id, actor_id=payload.actor_id, action="account-risk-assessed"))
        return record

    def _evaluate(self, payload: AccountRiskAssessmentCreate) -> tuple[AccountRiskState, list[str], str]:
        o, p = payload.observation, payload.policy
        if not payload.risk_brain_clear:
            return AccountRiskState.blocked, ["Risk Brain blocked account-risk processing"], "keep-account-blocked"
        if p.require_position_data and o.position_lifecycle_state not in {"position-open", "position-closed"}:
            return AccountRiskState.position_data_required, ["Governed position lifecycle data is required"], "resolve-position-lifecycle"
        reconciled = o.broker_snapshot_present and o.broker_balance_reconciled and o.broker_equity_reconciled and o.open_positions_reconciled
        if p.require_broker_reconciliation and not reconciled:
            return AccountRiskState.broker_reconciliation_required, ["Broker account or position snapshot is not reconciled"], "reconcile-broker-account"

        daily_loss_pct = max((o.start_of_day_balance - o.equity) / o.start_of_day_balance * 100, 0)
        if daily_loss_pct >= p.maximum_daily_loss_pct:
            return AccountRiskState.daily_loss_breached, ["Daily loss limit is reached or exceeded"], "block-new-risk-and-reduce"
        drawdown_pct = max((o.initial_account_balance - o.equity) / o.initial_account_balance * 100, 0)
        if drawdown_pct >= p.maximum_drawdown_pct:
            return AccountRiskState.drawdown_breached, ["Maximum account drawdown is reached or exceeded"], "freeze-account-and-reconcile"
        if o.used_margin > 0 and o.equity / o.used_margin * 100 < p.minimum_margin_level_pct:
            return AccountRiskState.margin_stressed, ["Margin level is below the governed minimum"], "reduce-margin-exposure"
        if o.largest_symbol_exposure_pct > p.maximum_symbol_exposure_pct or o.largest_strategy_exposure_pct > p.maximum_strategy_exposure_pct:
            return AccountRiskState.exposure_concentrated, ["Symbol or strategy exposure concentration exceeds policy"], "rebalance-or-reduce-concentration"
        if o.correlated_exposure_pct > p.maximum_correlated_exposure_pct:
            return AccountRiskState.correlation_breached, ["Correlated exposure exceeds policy"], "reduce-correlated-risk"
        if o.open_risk_pct > p.maximum_open_risk_pct or o.pending_order_risk_pct > p.maximum_pending_order_risk_pct:
            return AccountRiskState.risk_reduction_required, ["Open or pending-order risk exceeds policy"], "cancel-pending-risk-or-reduce-positions"
        if o.close_or_reduce_requested:
            if p.require_human_approval_for_reduction and not o.human_approval_verified:
                return AccountRiskState.risk_reduction_required, ["Explicit human approval is required for risk reduction"], "request-risk-reduction-approval"
            if not o.reduction_acknowledged:
                return AccountRiskState.risk_reduction_required, ["Broker has not acknowledged the risk-reduction action"], "query-risk-reduction-state"
        return AccountRiskState.account_risk_clear, ["Account risk and portfolio exposure are within governed limits"], "continue-monitored-operation"

    def list_assessments(self, workspace_id: str) -> list[AccountRiskAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> AccountRiskAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def reduce(self, request: RiskReductionRequest) -> AccountRiskAssessment:
        record = next((item for item in self._records.values() if item.workspace_id == request.workspace_id and item.assessment_id == request.assessment_id), None)
        if record is None:
            raise KeyError("Account-risk assessment not found")
        if not request.human_approval_verified:
            raise ValueError("Explicit human approval is required")
        if not request.reduction_acknowledged:
            record.state = AccountRiskState.risk_reduction_required
            record.reduction_required = True
            record.recommended_action = "query-risk-reduction-state"
            record.reasons = ["Broker acknowledgement for risk reduction is required"]
        else:
            record.state = AccountRiskState.account_risk_clear
            record.reduction_required = False
            record.total_open_risk_pct = request.updated_open_risk_pct
            record.margin_level_pct = None if request.updated_used_margin == 0 else request.updated_equity / request.updated_used_margin * 100
            record.recommended_action = "continue-monitored-operation"
            record.reasons = ["Approved risk reduction completed and account returned to monitored operation"]
        self._audit.append(AuditRecord(workspace_id=request.workspace_id, record_id=record.id, assessment_id=record.assessment_id, actor_id=request.actor_id, action="account-risk-reduction-assessed"))
        return record

    def status(self, workspace_id: str) -> AccountRiskStatusResponse:
        records = self.list_assessments(workspace_id)
        clear = sum(record.state == AccountRiskState.account_risk_clear for record in records)
        return AccountRiskStatusResponse(workspace_id=workspace_id, assessments=len(records), clear=clear, breached_or_attention=len(records) - clear, latest_state=records[-1].state if records else None)

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


executive_account_risk_service = ExecutiveAccountRiskService()
