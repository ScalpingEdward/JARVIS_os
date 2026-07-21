from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    PendingOrderAssessment,
    PendingOrderAssessmentCreate,
    PendingOrderExecuteRequest,
    PendingOrderState,
    PendingOrderStatus,
)


class PendingOrderOCOService:
    def __init__(self) -> None:
        self._records: dict[UUID, PendingOrderAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def _evaluate(self, payload: PendingOrderAssessmentCreate) -> tuple[PendingOrderState, list[str]]:
        reasons: list[str] = []
        if payload.risk_brain_blocked:
            return PendingOrderState.BLOCKED, ["Risk Brain blocked pending-order execution"]
        if not payload.profit_lock_ready:
            return PendingOrderState.PROFIT_LOCK_REQUIRED, ["v18.90 profit-lock dependency is not ready"]
        if payload.order_type not in {"buy_limit", "sell_limit", "buy_stop", "sell_stop", "buy_stop_limit", "sell_stop_limit"}:
            return PendingOrderState.REQUEST_INVALID, ["Unsupported MT5 pending-order type"]
        minimum_distance = max(payload.stop_level_points, payload.freeze_level_points) * payload.point
        if payload.order_type.startswith("buy") and payload.entry_price < payload.current_ask and "limit" not in payload.order_type:
            return PendingOrderState.PRICE_INVALID, ["Buy stop entry must be above current ask"]
        if payload.order_type.startswith("sell") and payload.entry_price > payload.current_bid and "limit" not in payload.order_type:
            return PendingOrderState.PRICE_INVALID, ["Sell stop entry must be below current bid"]
        reference_price = payload.current_ask if payload.order_type.startswith("buy") else payload.current_bid
        if abs(payload.entry_price - reference_price) < minimum_distance:
            return PendingOrderState.PRICE_INVALID, ["Pending entry violates stop or freeze distance"]
        if payload.expiration_at is not None and payload.expiration_at <= datetime.now(timezone.utc):
            return PendingOrderState.EXPIRATION_INVALID, ["Pending-order expiration must be in the future"]
        if payload.oco_group_id and not payload.peer_order_defined:
            return PendingOrderState.OCO_INVALID, ["OCO group requires a defined peer order"]
        if not payload.account_risk_approved or not payload.prop_rules_approved:
            return PendingOrderState.RISK_REJECTED, ["Account-risk and prop-rule approval are mandatory"]
        if not payload.human_approved:
            return PendingOrderState.APPROVAL_REQUIRED, ["Human approval is required"]
        if payload.terminal_error:
            return PendingOrderState.FAILED, [payload.terminal_error]
        if not payload.placement_dispatched:
            return PendingOrderState.PLACEMENT_PENDING, ["Pending-order placement has not been dispatched"]
        if not payload.broker_acknowledged or not payload.broker_order_id or payload.broker_retcode not in {10008, 10009}:
            return PendingOrderState.BROKER_ACK_PENDING, ["Broker acknowledgement or accepted retcode is missing"]
        if payload.oco_group_id and payload.peer_cancel_required and not payload.peer_cancel_acknowledged:
            return PendingOrderState.CANCEL_PENDING, ["OCO peer cancellation is still pending"]
        if payload.oco_group_id and not payload.peer_cancel_required:
            return PendingOrderState.OCO_ARMED, ["OCO pair is armed and awaiting trigger"]
        if not payload.pending_orders_reconciled or not payload.account_snapshot_reconciled:
            return PendingOrderState.RECONCILIATION_REQUIRED, ["Pending orders and account snapshot must reconcile"]
        return PendingOrderState.PENDING_READY, reasons

    def create(self, payload: PendingOrderAssessmentCreate) -> PendingOrderAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate source_key in workspace")
        state, reasons = self._evaluate(payload)
        record = PendingOrderAssessment(state=state, reasons=reasons, payload=payload)
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, action="assessment-created", actor_id=payload.actor_id, record_id=record.id))
        return record

    def execute(self, record_id: UUID, workspace_id: str, request: PendingOrderExecuteRequest) -> PendingOrderAssessment:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("Pending-order assessment not found")
        updated_payload = record.payload.model_copy(update=request.model_dump(exclude={"actor_id"}, exclude_none=True))
        state, reasons = self._evaluate(updated_payload)
        updated = record.model_copy(update={"payload": updated_payload, "state": state, "reasons": reasons})
        self._records[record_id] = updated
        self._audit.append(AuditRecord(workspace_id=workspace_id, action="pending-order-executed", actor_id=request.actor_id, record_id=record_id))
        return updated

    def get(self, record_id: UUID, workspace_id: str) -> PendingOrderAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.payload.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[PendingOrderAssessment]:
        return [record for record in self._records.values() if record.payload.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> PendingOrderStatus:
        records = self.list_records(workspace_id)
        return PendingOrderStatus(workspace_id=workspace_id, latest_state=records[-1].state if records else None, count=len(records))

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


pending_order_oco_service = PendingOrderOCOService()
