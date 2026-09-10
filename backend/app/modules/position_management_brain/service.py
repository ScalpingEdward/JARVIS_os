from __future__ import annotations

from datetime import datetime, timezone
from secrets import token_urlsafe

from app.db import SessionLocal
from app.db_models import (
    PositionManagementAuditRow,
    PositionManagementPayloadRow,
    PositionManagementRecordRow,
    PositionManagementUsedTokenRow,
)

from .models import AuditEvent, PositionAction, PositionCommand, PositionCreate, PositionRecord, PositionState


class PositionManagementError(RuntimeError):
    pass


class PositionManagementService:
    """Produces governed lifecycle recommendations; never places or modifies live trades.

    Persisted via the same SessionLocal infrastructure setup_submission
    and dynamic_risk_engine already use -- previously four in-memory
    structures (records, the original creation payloads, audit, and
    approval-token/receipt replay protection), all silently emptied on
    every restart.
    """

    def status(self) -> dict[str, object]:
        with SessionLocal() as session:
            count = session.query(PositionManagementRecordRow).count()
        return {
            "module": "position-management-brain", "version": "21.16", "status": "operational",
            "records": count, "safety_boundary": "recommendation-only-no-broker-execution",
        }

    def reset(self) -> None:
        """Needed now that storage is real and shared rather than
        fresh-per-instance in-memory."""
        with SessionLocal() as session:
            session.query(PositionManagementRecordRow).delete()
            session.query(PositionManagementPayloadRow).delete()
            session.query(PositionManagementAuditRow).delete()
            session.query(PositionManagementUsedTokenRow).delete()
            session.commit()

    def create(self, payload: PositionCreate, actor: str = "system") -> PositionRecord:
        with SessionLocal() as session:
            existing = (
                session.query(PositionManagementRecordRow)
                .filter(
                    PositionManagementRecordRow.workspace_id == payload.workspace_id,
                    PositionManagementRecordRow.source_key == payload.source_key,
                )
                .first()
            )
            if existing is not None:
                raise PositionManagementError(f"duplicate source_key; existing record={existing.id}")

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
            session.add(PositionManagementRecordRow(
                id=record.id, workspace_id=record.workspace_id, source_key=record.source_key,
                state=state.value, data=record.model_dump_json(),
            ))
            session.add(PositionManagementPayloadRow(record_id=record.id, data=payload.model_dump_json()))
            session.add(self._audit_row(record, actor, "create", None, state.value))
            session.commit()
        return record

    def list(self, workspace_id: str) -> list[PositionRecord]:
        with SessionLocal() as session:
            rows = session.query(PositionManagementRecordRow).filter(
                PositionManagementRecordRow.workspace_id == workspace_id
            ).all()
        return [PositionRecord.model_validate_json(r.data) for r in rows]

    def get(self, workspace_id: str, record_id: str) -> PositionRecord:
        with SessionLocal() as session:
            row = session.get(PositionManagementRecordRow, record_id)
        if row is None or row.workspace_id != workspace_id:
            raise PositionManagementError("record not found")
        return PositionRecord.model_validate_json(row.data)

    def execute(self, workspace_id: str, record_id: str, action: PositionAction) -> PositionRecord:
        with SessionLocal() as session:
            row = session.get(PositionManagementRecordRow, record_id)
            if row is None or row.workspace_id != workspace_id:
                raise PositionManagementError("record not found")
            record = PositionRecord.model_validate_json(row.data)
            payload_row = session.get(PositionManagementPayloadRow, record_id)
            payload = PositionCreate.model_validate_json(payload_row.data)
            before = record.state.value

            if action.command == PositionCommand.APPROVE:
                if record.state not in {PositionState.PLANNED, PositionState.HUMAN_REVIEW_REQUIRED}:
                    raise PositionManagementError("position plan is not approvable")
                token = action.approval_token or token_urlsafe(24)
                self._claim_token_or_raise(session, token, "approval_token")
                record.approval_token = token
                record.state = PositionState.APPROVED
            elif action.command == PositionCommand.MARK_OPEN:
                if record.state != PositionState.APPROVED:
                    raise PositionManagementError("only approved plans can be marked open")
                if not action.downstream_receipt:
                    raise PositionManagementError("downstream receipt is required")
                self._claim_token_or_raise(session, action.downstream_receipt, "downstream_receipt")
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
            row.state = record.state.value
            row.data = record.model_dump_json()
            session.add(self._audit_row(
                record, action.actor, action.command.value, before, record.state.value,
                {"rule_key": action.rule_key},
            ))
            session.commit()
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        with SessionLocal() as session:
            rows = (
                session.query(PositionManagementAuditRow)
                .filter(PositionManagementAuditRow.workspace_id == workspace_id)
                .order_by(PositionManagementAuditRow.created_at)
                .all()
            )
        return [AuditEvent.model_validate_json(r.data) for r in rows]

    @staticmethod
    def _claim_token_or_raise(session, token: str, kind: str) -> None:
        session.add(PositionManagementUsedTokenRow(token=token, kind=kind))
        try:
            session.flush()
        except Exception as exc:
            session.rollback()
            label = "approval token" if kind == "approval_token" else "downstream receipt"
            raise PositionManagementError(f"{label} replay detected") from exc

    @staticmethod
    def _audit_row(
        record: PositionRecord, actor: str, action: str, from_state: str | None,
        to_state: str, details: dict[str, object] | None = None,
    ) -> PositionManagementAuditRow:
        event = AuditEvent(
            workspace_id=record.workspace_id, record_id=record.id, action=action, actor=actor,
            from_state=from_state, to_state=to_state, details=details or {},
        )
        return PositionManagementAuditRow(
            id=event.id, workspace_id=event.workspace_id, created_at=event.created_at,
            data=event.model_dump_json(),
        )
