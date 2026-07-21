from uuid import UUID

from .models import (
    AuditRecord,
    StrategyRuntimeAssessment,
    StrategyRuntimeAssessmentCreate,
    StrategyRuntimeExecuteRequest,
    StrategyRuntimeState,
    StrategyRuntimeStatus,
)


class StrategyRuntimeOrchestratorService:
    def __init__(self) -> None:
        self._records: dict[UUID, StrategyRuntimeAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def _evaluate(self, payload: StrategyRuntimeAssessmentCreate) -> tuple[StrategyRuntimeState, list[str], list[str]]:
        if payload.risk_brain_blocked:
            return StrategyRuntimeState.BLOCKED, ["Risk Brain blocked strategy runtime"], []
        if not payload.portfolio_ready:
            return StrategyRuntimeState.PORTFOLIO_REQUIRED, ["v18.93 portfolio-ready dependency is missing"], []
        if payload.terminal_error:
            return StrategyRuntimeState.FAILED, [payload.terminal_error], []
        if payload.pause_requested:
            return StrategyRuntimeState.PAUSED, ["Runtime pause requested"], []

        eligible = [c for c in payload.candidates if c.enabled]
        if not eligible:
            return StrategyRuntimeState.STRATEGY_INVALID, ["No enabled strategy candidate"], []
        if any(c.side not in {"buy", "sell"} for c in eligible):
            return StrategyRuntimeState.STRATEGY_INVALID, ["Strategy side must be buy or sell"], []
        if any(c.signal_age_seconds > payload.max_signal_age_seconds for c in eligible):
            return StrategyRuntimeState.SIGNAL_STALE, ["At least one strategy signal is stale"], []
        if any(c.regime != payload.current_regime for c in eligible):
            return StrategyRuntimeState.REGIME_MISMATCH, ["Strategy regime does not match current regime"], []
        if any(c.confidence < payload.minimum_confidence or c.expected_rr < payload.minimum_expected_rr for c in eligible):
            return StrategyRuntimeState.STRATEGY_INVALID, ["Confidence or expected RR is below policy"], []

        by_symbol: dict[str, set[str]] = {}
        for candidate in eligible:
            by_symbol.setdefault(candidate.symbol, set()).add(candidate.side)
        if any(len(sides) > 1 for sides in by_symbol.values()):
            return StrategyRuntimeState.CONFLICT_DETECTED, ["Conflicting strategy directions detected for the same symbol"], []

        capacity = payload.max_concurrent_strategies - payload.active_strategy_count
        if capacity <= 0:
            return StrategyRuntimeState.CAPACITY_REJECTED, ["No strategy runtime capacity available"], []

        ordered = sorted(eligible, key=lambda c: (c.priority, -c.confidence, -c.expected_rr))
        selected = ordered[:capacity]
        selected_ids = [c.strategy_id for c in selected]
        total_risk = sum(c.requested_risk_amount for c in selected)
        if total_risk > payload.available_risk_budget:
            return StrategyRuntimeState.RISK_REJECTED, ["Selected strategies exceed available risk budget"], selected_ids
        if not payload.account_risk_approved or not payload.prop_rules_approved:
            return StrategyRuntimeState.RISK_REJECTED, ["Account-risk and prop-rule approval are mandatory"], selected_ids
        if not payload.human_approved:
            return StrategyRuntimeState.APPROVAL_REQUIRED, ["Human approval is required"], selected_ids
        if not payload.dispatch_requested:
            return StrategyRuntimeState.SCHEDULED, ["Strategies selected and awaiting dispatch"], selected_ids
        if not payload.dispatch_acknowledged:
            return StrategyRuntimeState.DISPATCH_PENDING, ["Runtime dispatch acknowledgement is missing"], selected_ids
        if not payload.execution_started:
            return StrategyRuntimeState.EXECUTION_PENDING, ["Strategy execution has not started"], selected_ids
        if not payload.runtime_reconciled:
            return StrategyRuntimeState.RECONCILIATION_REQUIRED, ["Runtime state must reconcile with execution adapters"], selected_ids
        return StrategyRuntimeState.RUNTIME_ACTIVE, [], selected_ids

    def create(self, payload: StrategyRuntimeAssessmentCreate) -> StrategyRuntimeAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate source_key in workspace")
        state, reasons, selected_ids = self._evaluate(payload)
        record = StrategyRuntimeAssessment(state=state, reasons=reasons, selected_strategy_ids=selected_ids, payload=payload)
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, action="assessment-created", actor_id=payload.actor_id, record_id=record.id))
        return record

    def execute(self, record_id: UUID, workspace_id: str, request: StrategyRuntimeExecuteRequest) -> StrategyRuntimeAssessment:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("Strategy runtime assessment not found")
        updated_payload = record.payload.model_copy(update=request.model_dump(exclude={"actor_id"}, exclude_none=True))
        state, reasons, selected_ids = self._evaluate(updated_payload)
        updated = record.model_copy(update={"payload": updated_payload, "state": state, "reasons": reasons, "selected_strategy_ids": selected_ids})
        self._records[record_id] = updated
        self._audit.append(AuditRecord(workspace_id=workspace_id, action="runtime-executed", actor_id=request.actor_id, record_id=record_id))
        return updated

    def get(self, record_id: UUID, workspace_id: str) -> StrategyRuntimeAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.payload.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[StrategyRuntimeAssessment]:
        return [record for record in self._records.values() if record.payload.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> StrategyRuntimeStatus:
        records = self.list_records(workspace_id)
        return StrategyRuntimeStatus(workspace_id=workspace_id, latest_state=records[-1].state if records else None, count=len(records))

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


strategy_runtime_orchestrator_service = StrategyRuntimeOrchestratorService()
