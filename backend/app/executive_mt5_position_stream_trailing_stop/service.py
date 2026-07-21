from datetime import datetime, timezone
from uuid import UUID

from .models import AuditRecord, PositionStreamCreate, PositionStreamRecord, PositionStreamState, PositionStreamStatusResponse, TrailingModifyRequest


class ExecutiveMT5PositionStreamTrailingStopService:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._records: dict[UUID, PositionStreamRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._stream_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def _evaluate(self, payload: PositionStreamCreate) -> tuple[PositionStreamState, list[str]]:
        o = payload.observation
        if not payload.risk_brain_clear:
            return PositionStreamState.blocked, ["Risk Brain blocked trailing-stop governance"]
        if o.lifecycle_state != "lifecycle-complete":
            return PositionStreamState.lifecycle_required, ["Position lifecycle is not complete"]
        if not payload.account_risk_clear or not payload.prop_rules_clear:
            return PositionStreamState.blocked, ["Account risk or prop rules blocked trailing modification"]
        if not o.stream_connected:
            return PositionStreamState.stream_unavailable, ["Position event stream is unavailable"]
        if not o.sequence_contiguous:
            return PositionStreamState.event_gap_detected, ["Position event sequence contains a gap"]
        if o.snapshot_age_seconds > o.max_snapshot_age_seconds:
            return PositionStreamState.stale_snapshot, ["Position snapshot is stale"]
        if not o.position_exists:
            return PositionStreamState.trailing_failed, ["Position no longer exists"]
        if not o.trailing_enabled:
            return PositionStreamState.trailing_inactive, ["Trailing stop is disabled"]
        favorable_points = ((o.current_price - o.entry_price) if o.side == "buy" else (o.entry_price - o.current_price)) / o.point_size
        if favorable_points < o.activation_distance_points:
            return PositionStreamState.trigger_not_reached, ["Trailing activation distance has not been reached"]
        if o.proposed_stop_loss is None or o.trailing_distance_points <= 0:
            return PositionStreamState.protection_invalid, ["Proposed trailing protection is incomplete"]
        minimum_distance = max(o.stop_level_points, o.freeze_level_points) * o.point_size
        price_distance = abs(o.current_price - o.proposed_stop_loss)
        if price_distance < minimum_distance:
            return PositionStreamState.protection_invalid, ["Proposed stop violates stop or freeze level"]
        if o.side == "buy" and o.proposed_stop_loss >= o.current_price:
            return PositionStreamState.protection_invalid, ["Buy stop must remain below current price"]
        if o.side == "sell" and o.proposed_stop_loss <= o.current_price:
            return PositionStreamState.protection_invalid, ["Sell stop must remain above current price"]
        if not o.human_approval_verified:
            return PositionStreamState.approval_required, ["Human approval is required"]
        if o.terminal_error:
            return PositionStreamState.trailing_failed, ["MT5 terminal reported an error"]
        if not o.modify_dispatched:
            return PositionStreamState.modify_pending, ["Trailing modification has not been dispatched"]
        if not o.modify_acknowledged or not o.broker_retcode_ok:
            return PositionStreamState.broker_ack_pending, ["Broker acknowledgement is pending"]
        if not all([o.resulting_stop_loss_verified, o.position_snapshot_reconciled, o.account_snapshot_reconciled]):
            return PositionStreamState.reconciliation_required, ["Trailing-stop reconciliation is incomplete"]
        return PositionStreamState.trailing_active, []

    def assess(self, payload: PositionStreamCreate) -> PositionStreamRecord:
        source_key = (payload.workspace_id, payload.source_key)
        stream_key = (payload.workspace_id, payload.stream_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate source key")
        if stream_key in self._stream_ids:
            raise ValueError("Duplicate stream id")
        state, reasons = self._evaluate(payload)
        record = PositionStreamRecord(workspace_id=payload.workspace_id, source_key=payload.source_key, actor_id=payload.actor_id, stream_id=payload.stream_id, position_ticket=payload.position_ticket, state=state, reasons=reasons, trailing_commands_enabled=state == PositionStreamState.trailing_active)
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._stream_ids.add(stream_key)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, action="assessed", actor_id=payload.actor_id, stream_id=record.stream_id, state=record.state))
        return record

    def execute(self, request: TrailingModifyRequest) -> PositionStreamRecord:
        record = next((item for item in self._records.values() if item.workspace_id == request.workspace_id and item.stream_id == request.stream_id), None)
        if record is None:
            raise KeyError("Position stream not found")
        if not request.human_approval_verified:
            raise ValueError("Human approval required")
        if request.terminal_error:
            record.state = PositionStreamState.trailing_failed
        elif not request.modify_dispatched:
            record.state = PositionStreamState.modify_pending
        elif not request.modify_acknowledged or not request.broker_retcode_ok:
            record.state = PositionStreamState.broker_ack_pending
        elif not all([request.resulting_stop_loss_verified, request.position_snapshot_reconciled, request.account_snapshot_reconciled]):
            record.state = PositionStreamState.reconciliation_required
        else:
            record.state = PositionStreamState.trailing_active
        record.trailing_commands_enabled = record.state == PositionStreamState.trailing_active
        record.updated_at = datetime.now(timezone.utc)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, action="trailing-modified", actor_id=request.actor_id, stream_id=record.stream_id, state=record.state))
        return record

    def get(self, record_id: UUID, workspace_id: str) -> PositionStreamRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[PositionStreamRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> PositionStreamStatusResponse:
        records = self.list_records(workspace_id)
        return PositionStreamStatusResponse(workspace_id=workspace_id, records=len(records), trailing_active=sum(r.state == PositionStreamState.trailing_active for r in records), blocked=sum(r.state == PositionStreamState.blocked for r in records))

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_mt5_position_stream_trailing_stop_service = ExecutiveMT5PositionStreamTrailingStopService()
