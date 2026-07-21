from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    BridgeStartRequest,
    MT5RuntimeBridgeCreate,
    MT5RuntimeBridgeRecord,
    MT5RuntimeBridgeState,
    MT5RuntimeBridgeStatusResponse,
)


class ExecutiveMT5RuntimeBridgeService:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._records: dict[UUID, MT5RuntimeBridgeRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._bridge_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def _evaluate(self, payload: MT5RuntimeBridgeCreate) -> tuple[MT5RuntimeBridgeState, list[str]]:
        observation = payload.observation
        if not payload.risk_brain_clear:
            return MT5RuntimeBridgeState.blocked, ["Risk Brain blocked MT5 bridge activation"]
        if observation.live_adapter_state != "production-ready":
            return MT5RuntimeBridgeState.activation_required, ["Live adapter activation is not production-ready"]
        if not all([
            observation.terminal_process_running,
            observation.terminal_version_verified,
            observation.terminal_path_verified,
            observation.market_connected,
        ]):
            return MT5RuntimeBridgeState.terminal_unavailable, ["MT5 terminal runtime is unavailable or unverified"]
        if (
            not observation.account_login_verified
            or observation.expected_account_login == 0
            or observation.observed_account_login != observation.expected_account_login
            or not observation.broker_server_verified
        ):
            return MT5RuntimeBridgeState.account_mismatch, ["MT5 account identity or broker server does not match"]
        if not all([
            observation.symbol_mapping_verified,
            observation.volume_step_verified,
            observation.filling_mode_verified,
            observation.stop_level_verified,
        ]):
            return MT5RuntimeBridgeState.symbol_mapping_required, ["Symbol or execution-constraint mapping is incomplete"]
        if not observation.trade_mode_enabled or not observation.algo_trading_enabled:
            return MT5RuntimeBridgeState.trading_permission_required, ["MT5 trading permissions are not enabled"]
        if (
            not observation.execution_probe_completed
            or observation.execution_probe_errors > 0
            or not observation.execution_probe_reconciled
        ):
            return MT5RuntimeBridgeState.execution_probe_required, ["A successful reconciled execution probe is required"]
        if not observation.human_approval_verified:
            return MT5RuntimeBridgeState.approval_required, ["Human approval is required before starting the MT5 bridge"]
        if not observation.bridge_started or not observation.bridge_acknowledged:
            return MT5RuntimeBridgeState.bridge_pending, ["MT5 bridge start acknowledgement is pending"]
        if not all([
            observation.positions_reconciled,
            observation.pending_orders_reconciled,
            observation.account_snapshot_reconciled,
        ]):
            return MT5RuntimeBridgeState.reconciliation_required, ["MT5 account state reconciliation is incomplete"]
        return MT5RuntimeBridgeState.bridge_ready, []

    def assess(self, payload: MT5RuntimeBridgeCreate) -> MT5RuntimeBridgeRecord:
        source_key = (payload.workspace_id, payload.source_key)
        bridge_key = (payload.workspace_id, payload.bridge_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate source key")
        if bridge_key in self._bridge_ids:
            raise ValueError("Duplicate bridge id")
        state, reasons = self._evaluate(payload)
        record = MT5RuntimeBridgeRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            bridge_id=payload.bridge_id,
            terminal_reference=payload.terminal_reference,
            account_reference=payload.account_reference,
            state=state,
            reasons=reasons,
            order_submission_enabled=state == MT5RuntimeBridgeState.bridge_ready,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._bridge_ids.add(bridge_key)
        self._audit.append(AuditRecord(
            workspace_id=record.workspace_id,
            action="assessed",
            actor_id=payload.actor_id,
            bridge_id=record.bridge_id,
            state=record.state,
        ))
        return record

    def start_bridge(self, request: BridgeStartRequest) -> MT5RuntimeBridgeRecord:
        record = next((
            item for item in self._records.values()
            if item.workspace_id == request.workspace_id and item.bridge_id == request.bridge_id
        ), None)
        if record is None:
            raise KeyError("MT5 bridge not found")
        if not request.human_approval_verified:
            raise ValueError("Human approval required")
        if not request.bridge_started or not request.bridge_acknowledged:
            record.state = MT5RuntimeBridgeState.bridge_pending
        elif not all([
            request.positions_reconciled,
            request.pending_orders_reconciled,
            request.account_snapshot_reconciled,
        ]):
            record.state = MT5RuntimeBridgeState.reconciliation_required
        else:
            record.state = MT5RuntimeBridgeState.bridge_ready
        record.order_submission_enabled = record.state == MT5RuntimeBridgeState.bridge_ready
        record.updated_at = datetime.now(timezone.utc)
        self._audit.append(AuditRecord(
            workspace_id=record.workspace_id,
            action="bridge-started",
            actor_id=request.actor_id,
            bridge_id=record.bridge_id,
            state=record.state,
        ))
        return record

    def get(self, record_id: UUID, workspace_id: str) -> MT5RuntimeBridgeRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[MT5RuntimeBridgeRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> MT5RuntimeBridgeStatusResponse:
        records = self.list_records(workspace_id)
        return MT5RuntimeBridgeStatusResponse(
            workspace_id=workspace_id,
            records=len(records),
            bridge_ready=sum(record.state == MT5RuntimeBridgeState.bridge_ready for record in records),
            blocked=sum(record.state == MT5RuntimeBridgeState.blocked for record in records),
        )

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_mt5_runtime_bridge_service = ExecutiveMT5RuntimeBridgeService()
