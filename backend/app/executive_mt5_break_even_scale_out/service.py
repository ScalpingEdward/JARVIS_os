from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    BreakEvenAssessment,
    BreakEvenAssessmentCreate,
    BreakEvenState,
    BreakEvenStatusResponse,
)


class ExecutiveMT5BreakEvenScaleOutService:
    def __init__(self) -> None:
        self._records: dict[UUID, BreakEvenAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def status(self, workspace_id: str) -> BreakEvenStatusResponse:
        return BreakEvenStatusResponse(
            workspace_id=workspace_id,
            assessments=len(self.list_records(workspace_id)),
        )

    def create(self, payload: BreakEvenAssessmentCreate, actor_id: str) -> BreakEvenAssessment:
        duplicate_key = (payload.workspace_id, payload.source_key)
        if duplicate_key in self._source_keys:
            raise ValueError("Duplicate source_key for workspace")

        state, proposed_stop_loss, close_volume, remaining_volume = self._evaluate(payload)
        record = BreakEvenAssessment(
            **payload.model_dump(),
            state=state,
            proposed_stop_loss=proposed_stop_loss,
            close_volume=close_volume,
            remaining_volume=remaining_volume,
        )
        self._records[record.id] = record
        self._source_keys.add(duplicate_key)
        self._write_audit(record, "assessment-created", actor_id)
        return record

    def execute(self, record_id: UUID, workspace_id: str, actor_id: str) -> BreakEvenAssessment:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("Break-even assessment not found")
        state, proposed_stop_loss, close_volume, remaining_volume = self._evaluate(record)
        record.state = state
        record.proposed_stop_loss = proposed_stop_loss
        record.close_volume = close_volume
        record.remaining_volume = remaining_volume
        record.updated_at = datetime.now(timezone.utc)
        self._write_audit(record, "execution-evaluated", actor_id)
        return record

    def list_records(self, workspace_id: str) -> list[BreakEvenAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> BreakEvenAssessment | None:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            return None
        return record

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _evaluate(self, payload: BreakEvenAssessmentCreate) -> tuple[BreakEvenState, float | None, float, float]:
        if payload.risk_brain_blocked:
            return BreakEvenState.BLOCKED, None, 0.0, payload.current_volume
        if payload.trailing_state != "trailing-active":
            return BreakEvenState.TRAILING_REQUIRED, None, 0.0, payload.current_volume
        if payload.terminal_error:
            return BreakEvenState.FAILED, None, 0.0, payload.current_volume
        if payload.position_ticket <= 0:
            return BreakEvenState.POSITION_MISSING, None, 0.0, payload.current_volume

        side = payload.side.lower()
        favorable_points = (
            (payload.current_price - payload.entry_price) / payload.point_size
            if side == "buy"
            else (payload.entry_price - payload.current_price) / payload.point_size
        )
        if favorable_points < payload.trigger_points:
            return BreakEvenState.TRIGGER_NOT_REACHED, None, 0.0, payload.current_volume

        buffer_points = payload.break_even_offset_points + payload.spread_points + payload.commission_points
        proposed_stop = (
            payload.entry_price + buffer_points * payload.point_size
            if side == "buy"
            else payload.entry_price - buffer_points * payload.point_size
        )
        distance_points = abs(payload.current_price - proposed_stop) / payload.point_size
        if distance_points < max(payload.stop_level_points, payload.freeze_level_points):
            return BreakEvenState.BREAK_EVEN_INVALID, proposed_stop, 0.0, payload.current_volume

        close_volume = 0.0
        remaining_volume = payload.current_volume
        if payload.scale_out_percent:
            if payload.observed_rr < payload.minimum_rr:
                return BreakEvenState.SCALE_OUT_INVALID, proposed_stop, 0.0, payload.current_volume
            raw_close = payload.current_volume * payload.scale_out_percent / 100
            steps = int(raw_close / payload.volume_step)
            close_volume = round(steps * payload.volume_step, 8)
            remaining_volume = round(payload.current_volume - close_volume, 8)
            if close_volume <= 0 or remaining_volume < payload.minimum_remaining_volume:
                return BreakEvenState.SCALE_OUT_INVALID, proposed_stop, close_volume, remaining_volume

        if not payload.risk_approved or not payload.prop_rules_approved:
            return BreakEvenState.RISK_REJECTED, proposed_stop, close_volume, remaining_volume
        if not payload.human_approved:
            return BreakEvenState.APPROVAL_REQUIRED, proposed_stop, close_volume, remaining_volume
        if not payload.command_dispatched:
            return BreakEvenState.COMMAND_PENDING, proposed_stop, close_volume, remaining_volume
        if not payload.broker_acknowledged:
            return BreakEvenState.BROKER_ACK_PENDING, proposed_stop, close_volume, remaining_volume
        if payload.broker_retcode not in {10008, 10009}:
            return BreakEvenState.FAILED, proposed_stop, close_volume, remaining_volume
        if close_volume > 0 and not payload.deal_event_received:
            return BreakEvenState.DEAL_EVENT_PENDING, proposed_stop, close_volume, remaining_volume
        if payload.resulting_stop_loss is None or abs(payload.resulting_stop_loss - proposed_stop) > payload.point_size:
            return BreakEvenState.RECONCILIATION_REQUIRED, proposed_stop, close_volume, remaining_volume
        if close_volume > 0 and payload.resulting_volume is None:
            return BreakEvenState.RECONCILIATION_REQUIRED, proposed_stop, close_volume, remaining_volume
        if not payload.position_reconciled or not payload.account_reconciled:
            return BreakEvenState.RECONCILIATION_REQUIRED, proposed_stop, close_volume, remaining_volume
        return BreakEvenState.PROFIT_LOCKED, proposed_stop, close_volume, remaining_volume

    def _write_audit(self, record: BreakEvenAssessment, action: str, actor_id: str) -> None:
        self._audit.append(
            AuditRecord(
                workspace_id=record.workspace_id,
                record_id=record.id,
                action=action,
                state=record.state,
                actor_id=actor_id,
            )
        )


executive_mt5_break_even_scale_out_service = ExecutiveMT5BreakEvenScaleOutService()
