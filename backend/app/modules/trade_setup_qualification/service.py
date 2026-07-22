from __future__ import annotations

from datetime import datetime, timezone
from secrets import token_urlsafe

from .models import (
    AuditEvent,
    QualificationResult,
    SetupAction,
    SetupCommand,
    SetupState,
    TradeSetupCreate,
    TradeSetupRecord,
)


class TradeSetupError(RuntimeError):
    pass


class TradeSetupQualificationService:
    """Qualifies trade setups but never places, modifies or closes trades."""

    def __init__(self) -> None:
        self._records: dict[str, TradeSetupRecord] = {}
        self._source_index: dict[tuple[str, str], str] = {}
        self._audit: list[AuditEvent] = []
        self._used_approval_tokens: set[str] = set()
        self._used_receipts: set[str] = set()

    def status(self) -> dict[str, object]:
        return {
            "module": "trade-setup-qualification",
            "version": "21.15",
            "status": "operational",
            "records": len(self._records),
            "safety_boundary": "qualification-only-no-execution",
        }

    def create(self, payload: TradeSetupCreate, actor: str = "system") -> TradeSetupRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_index:
            raise TradeSetupError(f"duplicate source_key; existing record={self._source_index[key]}")

        qualification = self._qualify(payload)
        if payload.risk_brain_hard_block:
            state = SetupState.BLOCKED
            qualification.blocking_reasons.append("Risk Brain hard block is authoritative.")
        elif not payload.v21_14_approved or not payload.v21_14_evidence:
            state = SetupState.EVIDENCE_REQUIRED
            qualification.blocking_reasons.append("Approved PHOENIX v21.14 evidence is mandatory.")
        elif qualification.blocking_reasons:
            state = SetupState.BLOCKED
        elif payload.active_news_risk:
            state = SetupState.HUMAN_REVIEW_REQUIRED
            qualification.warnings.append("Active news risk requires explicit human review.")
        elif qualification.confirmation_score < payload.minimum_confirmation_score:
            state = SetupState.HUMAN_REVIEW_REQUIRED
        elif min(qualification.risk_reward_ratios) < payload.minimum_rr:
            state = SetupState.HUMAN_REVIEW_REQUIRED
        elif payload.confidence_score < 60:
            state = SetupState.HUMAN_REVIEW_REQUIRED
        else:
            state = SetupState.QUALIFIED

        record = TradeSetupRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            market_structure_record_id=payload.market_structure_record_id,
            symbol=payload.symbol.upper(),
            timeframe=payload.timeframe,
            direction=payload.direction,
            state=state,
            entry_price=payload.entry_price,
            stop_price=payload.stop_price,
            target_prices=payload.target_prices,
            confidence_score=payload.confidence_score,
            qualification=qualification,
        )
        self._records[record.id] = record
        self._source_index[key] = record.id
        self._append_audit(record, actor, "create", None, state.value)
        return record

    def list(self, workspace_id: str) -> list[TradeSetupRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> TradeSetupRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise TradeSetupError("record not found")
        return record

    def execute(self, workspace_id: str, record_id: str, action: SetupAction) -> TradeSetupRecord:
        record = self.get(workspace_id, record_id)
        before = record.state.value

        if action.command == SetupCommand.APPROVE:
            if record.state not in {SetupState.QUALIFIED, SetupState.HUMAN_REVIEW_REQUIRED}:
                raise TradeSetupError("setup is not approvable")
            token = action.approval_token or token_urlsafe(24)
            if token in self._used_approval_tokens:
                raise TradeSetupError("approval token replay detected")
            self._used_approval_tokens.add(token)
            record.approval_token = token
            record.state = SetupState.APPROVED
        elif action.command == SetupCommand.ISSUE:
            if record.state != SetupState.APPROVED:
                raise TradeSetupError("only approved setups can be issued")
            if not action.downstream_receipt:
                raise TradeSetupError("downstream receipt is required")
            if action.downstream_receipt in self._used_receipts:
                raise TradeSetupError("downstream receipt replay detected")
            self._used_receipts.add(action.downstream_receipt)
            record.downstream_receipt = action.downstream_receipt
            record.state = SetupState.ISSUED_TO_VISUALIZER
        elif action.command == SetupCommand.REJECT:
            if record.state in {SetupState.ISSUED_TO_VISUALIZER, SetupState.ARCHIVED}:
                raise TradeSetupError("terminal setup cannot be rejected")
            record.state = SetupState.REJECTED
        elif action.command == SetupCommand.INVALIDATE:
            if record.state == SetupState.ARCHIVED:
                raise TradeSetupError("archived setup cannot be invalidated")
            record.state = SetupState.INVALIDATED
        elif action.command == SetupCommand.ARCHIVE:
            record.state = SetupState.ARCHIVED

        if action.reason:
            record.notes.append(action.reason)
        record.updated_at = datetime.now(timezone.utc)
        self._append_audit(record, action.actor, action.command.value, before, record.state.value)
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    @staticmethod
    def _qualify(payload: TradeSetupCreate) -> QualificationResult:
        total_weight = sum(item.weight for item in payload.confirmations)
        passed_weight = sum(item.weight for item in payload.confirmations if item.present and item.evidence_ref)
        score = round(passed_weight / max(total_weight, 1) * 100, 2)
        passed = [item.key for item in payload.confirmations if item.present and item.evidence_ref]
        failed = [item.key for item in payload.confirmations if not item.present or not item.evidence_ref]
        risk = abs(payload.entry_price - payload.stop_price)
        if risk == 0:
            raise TradeSetupError("entry and stop cannot be equal")
        rr = [round(abs(target - payload.entry_price) / risk, 3) for target in payload.target_prices]
        blocking: list[str] = []
        warnings: list[str] = []
        if payload.direction == "neutral":
            blocking.append("Neutral directional bias cannot become an executable setup.")
        if not payload.session_allowed:
            blocking.append("Current session is outside the governed trading window.")
        if payload.spread_points > payload.maximum_spread_points:
            blocking.append("Spread exceeds the configured execution threshold.")
        if any(not item.evidence_ref for item in payload.confirmations if item.present):
            warnings.append("One or more present confirmations lack evidence references.")
        if score >= 90 and min(rr) >= 3 and payload.confidence_score >= 85:
            grade = "A+"
        elif score >= 80 and min(rr) >= 2 and payload.confidence_score >= 75:
            grade = "A"
        elif score >= 70 and min(rr) >= 1.5:
            grade = "B"
        elif score >= 55:
            grade = "C"
        else:
            grade = "rejected"
        if blocking:
            grade = "rejected"
        return QualificationResult(
            confirmation_score=score,
            risk_reward_ratios=rr,
            passed_confirmations=passed,
            failed_confirmations=failed,
            blocking_reasons=blocking,
            warnings=warnings,
            setup_grade=grade,
        )

    def _append_audit(
        self,
        record: TradeSetupRecord,
        actor: str,
        action: str,
        from_state: str | None,
        to_state: str,
    ) -> None:
        self._audit.append(AuditEvent(
            workspace_id=record.workspace_id,
            record_id=record.id,
            action=action,
            actor=actor,
            from_state=from_state,
            to_state=to_state,
            details={"grade": record.qualification.setup_grade},
        ))
