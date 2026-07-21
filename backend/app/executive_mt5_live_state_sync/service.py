from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AccountSnapshot,
    LiveSyncAudit,
    LiveSyncCreate,
    LiveSyncExecuteRequest,
    LiveSyncRecord,
    LiveSyncState,
    LiveSyncStatus,
)
from .native_sync import NativeMT5StateProvider


class LiveStateSyncService:
    def __init__(self, provider: NativeMT5StateProvider | None = None):
        self.provider = provider
        self._records: dict[UUID, LiveSyncRecord] = {}
        self._audits: list[LiveSyncAudit] = []

    def set_provider(self, provider: NativeMT5StateProvider) -> None:
        self.provider = provider

    def create(self, payload: LiveSyncCreate) -> LiveSyncRecord:
        if any(r.workspace_id == payload.workspace_id and r.source_key == payload.source_key for r in self._records.values()):
            raise ValueError("duplicate source_key in workspace")
        state, detail = self._initial_state(payload)
        record = LiveSyncRecord(workspace_id=payload.workspace_id, source_key=payload.source_key, state=state, detail=detail, request=payload)
        self._records[record.id] = record
        self._audit(record, payload.actor_id, "create")
        return record

    @staticmethod
    def _initial_state(payload: LiveSyncCreate) -> tuple[LiveSyncState, str]:
        if payload.risk_brain_blocked:
            return LiveSyncState.BLOCKED, "Risk Brain blocked synchronization"
        if not payload.executor_reconciliation_required:
            return LiveSyncState.EXECUTOR_REQUIRED, "v19.01 reconciliation-required evidence is mandatory"
        if payload.account_login not in payload.approved_account_logins:
            return LiveSyncState.ACCOUNT_MISMATCH, "account login is not approved"
        if not payload.account_risk_approved or not payload.prop_rules_approved:
            return LiveSyncState.BLOCKED, "account-risk and prop-rule approval are mandatory"
        return LiveSyncState.SYNC_PENDING, "native terminal snapshot is ready to be requested"

    def execute(self, record_id: UUID, workspace_id: str, request: LiveSyncExecuteRequest) -> LiveSyncRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("live synchronization record not found")
        if request.human_recovery_approved is not None:
            record.request.human_recovery_approved = request.human_recovery_approved
        if request.action not in {"synchronize", "resynchronize", "complete-reconciliation"}:
            raise ValueError("unsupported synchronization action")
        if request.action == "complete-reconciliation":
            if record.state != LiveSyncState.SYNCHRONIZED:
                raise ValueError("only synchronized records can complete reconciliation")
            record.state = LiveSyncState.RECONCILIATION_COMPLETE
            record.detail = "broker and JARVIS state reconciliation completed"
            self._touch(record, request.actor_id, request.action)
            return record
        if record.state not in {LiveSyncState.SYNC_PENDING, LiveSyncState.RESYNC_REQUIRED, LiveSyncState.DRIFT_DETECTED, LiveSyncState.MANUAL_TRADE_DETECTED, LiveSyncState.PARTIAL_CLOSE_DETECTED}:
            raise ValueError(f"record cannot synchronize from state {record.state}")
        if request.action == "resynchronize" and not record.request.human_recovery_approved:
            raise ValueError("human recovery approval is required for resynchronization")
        if self.provider is None:
            self.provider = NativeMT5StateProvider()
        snapshot = self.provider.snapshot(record.request.history_from_epoch)
        self._reconcile(record, snapshot)
        self._touch(record, request.actor_id, request.action)
        return record

    def _reconcile(self, record: LiveSyncRecord, snapshot: dict) -> None:
        account = snapshot["account"]
        login = int(account.get("login", 0))
        if login != record.request.account_login or login not in record.request.approved_account_logins:
            record.state = LiveSyncState.ACCOUNT_MISMATCH
            record.detail = "terminal account does not match approved account"
            return
        record.account = AccountSnapshot(
            login=login,
            balance=float(account.get("balance", 0)),
            equity=float(account.get("equity", 0)),
            margin=float(account.get("margin", 0)),
            margin_free=float(account.get("margin_free", 0)),
            margin_level=float(account.get("margin_level", 0)),
            floating_profit=float(account.get("profit", 0)),
            daily_profit=sum(float(d.get("profit", 0)) + float(d.get("swap", 0)) + float(d.get("commission", 0)) for d in snapshot["deals"]),
        )
        position_map = {int(p.get("ticket", 0)): p for p in snapshot["positions"] if int(p.get("ticket", 0)) > 0}
        order_map = {int(o.get("ticket", 0)): o for o in snapshot["orders"] if int(o.get("ticket", 0)) > 0}
        deal_tickets = {int(d.get("ticket", 0)) for d in snapshot["deals"] if int(d.get("ticket", 0)) > 0}
        expected_positions = {item.broker_ticket: item for item in record.request.expected_positions}
        expected_orders = {item.broker_ticket: item for item in record.request.expected_orders}
        record.position_tickets = sorted(position_map)
        record.order_tickets = sorted(order_map)
        record.deal_tickets = sorted(deal_tickets)
        record.missing_position_tickets = sorted(set(expected_positions) - set(position_map))
        record.missing_order_tickets = sorted(set(expected_orders) - set(order_map))
        record.partial_close_tickets = sorted(ticket for ticket, expected in expected_positions.items() if ticket in position_map and float(position_map[ticket].get("volume", 0)) < expected.volume)
        known_tickets = set(expected_positions) | set(expected_orders)
        record.manual_trade_tickets = sorted((set(position_map) | set(order_map)) - known_tickets)
        missing_deals = sorted(set(record.request.expected_deal_tickets) - deal_tickets)
        if record.partial_close_tickets:
            record.state = LiveSyncState.PARTIAL_CLOSE_DETECTED
            record.detail = "partial close detected; recovery review required"
        elif record.manual_trade_tickets:
            record.state = LiveSyncState.MANUAL_TRADE_DETECTED
            record.detail = "manual or external terminal trade detected"
        elif record.missing_position_tickets:
            record.state = LiveSyncState.POSITION_MISMATCH
            record.detail = "expected positions are missing from terminal"
        elif record.missing_order_tickets:
            record.state = LiveSyncState.ORDER_MISMATCH
            record.detail = "expected pending orders are missing from terminal"
        elif missing_deals:
            record.state = LiveSyncState.DEAL_MISMATCH
            record.detail = "expected deals are missing from terminal history"
        else:
            record.state = LiveSyncState.SYNCHRONIZED
            record.detail = "account, positions, orders and deals match terminal state"

    def list_records(self, workspace_id: str) -> list[LiveSyncRecord]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> LiveSyncRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> LiveSyncStatus:
        records = self.list_records(workspace_id)
        return LiveSyncStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            synchronized_records=sum(r.state in {LiveSyncState.SYNCHRONIZED, LiveSyncState.RECONCILIATION_COMPLETE} for r in records),
            drift_records=sum(r.state in {LiveSyncState.ORDER_MISMATCH, LiveSyncState.POSITION_MISMATCH, LiveSyncState.DEAL_MISMATCH, LiveSyncState.MANUAL_TRADE_DETECTED, LiveSyncState.PARTIAL_CLOSE_DETECTED, LiveSyncState.DRIFT_DETECTED, LiveSyncState.RESYNC_REQUIRED} for r in records),
        )

    def audit_records(self, workspace_id: str) -> list[LiveSyncAudit]:
        return [a for a in self._audits if a.workspace_id == workspace_id]

    def _touch(self, record: LiveSyncRecord, actor_id: str, action: str) -> None:
        record.updated_at = datetime.now(timezone.utc)
        self._audit(record, actor_id, action)

    def _audit(self, record: LiveSyncRecord, actor_id: str, action: str) -> None:
        self._audits.append(LiveSyncAudit(record_id=record.id, workspace_id=record.workspace_id, actor_id=actor_id, action=action, state=record.state, detail=record.detail))


live_state_sync_service = LiveStateSyncService()
