from __future__ import annotations

from datetime import datetime, timezone
from secrets import token_urlsafe

from .models import AuditEvent, PositionAction, PositionCommand, PositionCreate, PositionRecord, PositionState


class PositionManagementError(RuntimeError):
    pass


class PositionManagementService:
    """Produces governed lifecycle recommendations; never places or modifies live trades."""

    def __init__(self) -> None:
        self._records: dict[str, PositionRecord] = {}
        self._payloads: dict[str, PositionCreate] = {}
        self._source_index: dict[tuple[str, str], str] = {}
        self._audit: list[AuditEvent] = []
        self._used_tokens: set[str] = set()
        self._used_receipts: set[str] = set()

    def status(self) -> dict[str, object]:
        return {"module": "position-management-brain", "version": "21.16", "status": "operational", "records": len(self._records), "safety_boundary": "recommendation-only-no-broker-execution"}

    def create(self, payload: PositionCreate, actor: str = "system") -> PositionRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_index:
            raise PositionManagementError(f"duplicate source_key; existing record={self._source_index[key]}")
        recommendations: list[str] = []
        if payload.risk_brain_hard_block:
            state = PositionState.BLOCKED
            recommendations.append("Risk Brain hard block is authoritative.")
        elif not payload.v21_15_approved or not payload.v21_15_evidence:
            state = PositionState.EVIDENCE_REQUIRED
            recommendations.append("Approved PHOENIX v21.15 evidence is mandatory.")
        elif payload.active_news_risk:
            state = PositionState.HUMAN_REVIEW_REQUIRED
            recommendations.append("Active news risk requires explicit human review.")
        else:
            state = PositionState.PLANNED
        record = PositionRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            trade_setup_record_id=payload.trade_setup_record_id,
            symbol=payload.symbol,
            direction=payload.direction,
            state=state,
            entry_price=payload.entry_price,
            current_stop_price=payload.initial_stop_price,
            position_size=payload.position_size,
            risk_amount=payload.risk_amount,
            recommendations=recommendations,
        )
        self._records[record.id] = record
        self._payloads[record.id] = payload
        self._source_index[key] = record.id
        self._log(record, actor, "create", None, state.value)
        return record

    def list(self, workspace_id: str) -> list[PositionRecord]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> PositionRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise PositionManagementError("record not found")
        return record

    def execute(self, workspace_id: str, record_id: str, action: PositionAction) -> PositionRecord:
        record = self.get(workspace_id, record_id)
        payload = self._payloads[record_id]
        before = record.state.value
        if action.command == PositionCommand.APPROVE:
            if record.state not in {PositionState.PLANNED, PositionState.HUMAN_REVIEW_REQUIRED}:
                raise PositionManagementError("position plan is not approvable")
            token = action.approval_token or token_urlsafe(24)
            if token in self._used_tokens:
                raise PositionManagementError("approval token replay detected")
            self._used_tokens.add(token)
            record.approval_token = token
            record.state = PositionState.APPROVED
        elif action.command == PositionCommand.MARK_OPEN:
            if record.state != PositionState.APPROVED:
                raise PositionManagementError("only approved plans can be marked open")
            if not action.downstream_receipt:
                raise PositionManagementError("downstream receipt is required")
            if action.downstream_receipt in self._used_receipts:
                raise PositionManagementError("downstream receipt replay detected")
            self._used_receipts.add(action.downstream_receipt)
            record.downstream_receipt = action.downstream_receipt
            record.state = PositionState.OPEN
        elif action.command == PositionCommand.APPLY_RULE:
            if record.state not in {PositionState.OPEN, PositionState.PROTECTED, PositionState.SCALING_OUT}:
                raise PositionManagementError("position is not manageable")
            rule = next((r for r in payload.exit_rules if r.key == action.rule_key), None)
            if not rule:
                raise PositionManagementError("rule not found")
            if rule.key in record.active_rule_keys:
                raise PositionManagementError("rule already applied")
            record.active_rule_keys.append(rule.key)
            if rule.stop_price is not None:
                if record.direction == "long" and rule.stop_price < record.current_stop_price:
                    raise PositionManagementError("long stop cannot be loosened")
                if record.direction == "short" and rule.stop_price > record.current_stop_price:
                    raise PositionManagementError("short stop cannot be loosened")
                record.current_stop_price = rule.stop_price
                record.state = PositionState.PROTECTED
            if rule.close_percent:
                record.remaining_percent = round(max(0, record.remaining_percent - rule.close_percent), 2)
                record.state = PositionState.CLOSED if record.remaining_percent == 0 else PositionState.SCALING_OUT
            if rule.kind in {"time-exit", "news-exit", "structure-exit"}:
                record.state = PositionState.EXIT_RECOMMENDED
                record.recommendations.append(f"Exit recommended by rule {rule.key}.")
        elif action.command == PositionCommand.RECOMMEND_EXIT:
            record.state = PositionState.EXIT_RECOMMENDED
            record.recommendations.append(action.reason or "Governed exit recommended.")
        elif action.command == PositionCommand.CLOSE:
            if record.state == PositionState.ARCHIVED:
                raise PositionManagementError("archived position cannot be closed")
            record.remaining_percent = 0
            record.realized_r_multiple = action.realized_r_multiple or record.realized_r_multiple
            record.state = PositionState.CLOSED
        elif action.command == PositionCommand.INVALIDATE:
            record.state = PositionState.INVALIDATED
        elif action.command == PositionCommand.ARCHIVE:
            record.state = PositionState.ARCHIVED
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, action.actor, action.command.value, before, record.state.value, {"rule_key": action.rule_key})
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [e for e in self._audit if e.workspace_id == workspace_id]

    def _log(self, record: PositionRecord, actor: str, action: str, from_state: str | None, to_state: str, details: dict[str, object] | None = None) -> None:
        self._audit.append(AuditEvent(workspace_id=record.workspace_id, record_id=record.id, action=action, actor=actor, from_state=from_state, to_state=to_state, details=details or {}))
