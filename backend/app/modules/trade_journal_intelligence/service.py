from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from threading import RLock
from typing import Dict, List, Optional

from .models import (
    AuditEvent,
    JournalAction,
    JournalAnalytics,
    JournalCommand,
    JournalState,
    TradeJournalCreate,
    TradeJournalRecord,
    TradeOutcome,
)


class JournalError(ValueError):
    pass


class TradeJournalIntelligenceService:
    def __init__(self) -> None:
        self._records: Dict[str, TradeJournalRecord] = {}
        self._audit: List[AuditEvent] = []
        self._source_keys: Dict[str, set[str]] = defaultdict(set)
        self._approval_tokens: set[str] = set()
        self._receipts: set[str] = set()
        self._lock = RLock()

    def create(self, payload: TradeJournalCreate, actor: str = "system") -> TradeJournalRecord:
        with self._lock:
            if payload.source_key in self._source_keys[payload.workspace_id]:
                raise JournalError("duplicate source_key in workspace")

            if payload.risk_brain_blocked:
                state = JournalState.BLOCKED
                analytics = None
            elif not payload.upstream_evidence_verified:
                state = JournalState.EVIDENCE_REQUIRED
                analytics = None
            else:
                analytics = self._analyze(payload)
                state = (
                    JournalState.HUMAN_REVIEW_REQUIRED
                    if analytics.process_flags
                    else JournalState.ANALYZED
                )

            record = TradeJournalRecord(
                **payload.dict(exclude={"upstream_evidence_verified", "risk_brain_blocked"}),
                state=state,
                analytics=analytics,
            )
            self._records[record.id] = record
            self._source_keys[payload.workspace_id].add(payload.source_key)
            self._append_audit(record, "created", actor, None, state)
            return record.copy(deep=True)

    def get(self, workspace_id: str, record_id: str) -> TradeJournalRecord:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.workspace_id != workspace_id:
                raise JournalError("record not found")
            return record.copy(deep=True)

    def list(self, workspace_id: str) -> List[TradeJournalRecord]:
        with self._lock:
            return [r.copy(deep=True) for r in self._records.values() if r.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> List[AuditEvent]:
        with self._lock:
            return [e.copy(deep=True) for e in self._audit if e.workspace_id == workspace_id]

    def act(self, workspace_id: str, record_id: str, action: JournalAction) -> TradeJournalRecord:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.workspace_id != workspace_id:
                raise JournalError("record not found")

            previous = record.state
            if action.command == JournalCommand.APPROVE:
                if previous not in {JournalState.ANALYZED, JournalState.HUMAN_REVIEW_REQUIRED}:
                    raise JournalError("record is not approvable")
                if not action.approval_token:
                    raise JournalError("approval token required")
                if action.approval_token in self._approval_tokens:
                    raise JournalError("approval token replay detected")
                self._approval_tokens.add(action.approval_token)
                record.approval_token = action.approval_token
                record.state = JournalState.APPROVED

            elif action.command == JournalCommand.ISSUE:
                if previous != JournalState.APPROVED:
                    raise JournalError("record must be approved before issue")
                if not action.downstream_receipt:
                    raise JournalError("downstream receipt required")
                if action.downstream_receipt in self._receipts:
                    raise JournalError("downstream receipt replay detected")
                self._receipts.add(action.downstream_receipt)
                record.downstream_receipt = action.downstream_receipt
                record.state = JournalState.ISSUED

            elif action.command == JournalCommand.REJECT:
                record.state = JournalState.REJECTED
            elif action.command == JournalCommand.INVALIDATE:
                record.state = JournalState.INVALIDATED
            elif action.command == JournalCommand.ARCHIVE:
                if previous not in {JournalState.ISSUED, JournalState.REJECTED, JournalState.INVALIDATED}:
                    raise JournalError("only terminal records can be archived")
                record.state = JournalState.ARCHIVED
            else:
                raise JournalError("unsupported command")

            record.updated_at = datetime.now(timezone.utc)
            self._append_audit(
                record,
                action.command.value,
                action.actor,
                previous,
                record.state,
                {"reason": action.reason} if action.reason else {},
            )
            return record.copy(deep=True)

    def summary(self, workspace_id: str) -> Dict[str, object]:
        records = [r for r in self.list(workspace_id) if r.analytics is not None]
        if not records:
            return {"trades": 0, "win_rate": 0.0, "average_r": 0.0, "expectancy_r": 0.0}
        wins = sum(1 for r in records if r.analytics and r.analytics.outcome == TradeOutcome.WIN)
        average_r = sum(r.realized_r_multiple for r in records) / len(records)
        return {
            "trades": len(records),
            "win_rate": round(wins / len(records) * 100, 2),
            "average_r": round(average_r, 4),
            "expectancy_r": round(average_r, 4),
        }

    @staticmethod
    def _analyze(payload: TradeJournalCreate) -> JournalAnalytics:
        if payload.realized_r_multiple > 0.05:
            outcome = TradeOutcome.WIN
        elif payload.realized_r_multiple < -0.05:
            outcome = TradeOutcome.LOSS
        else:
            outcome = TradeOutcome.BREAKEVEN

        discipline = 100.0
        flags: List[str] = []
        strengths: List[str] = []
        actions: List[str] = []

        if not payload.followed_plan:
            discipline -= 35
            flags.append("plan-deviation")
            actions.append("review entry and management deviations before next session")
        else:
            strengths.append("trade plan followed")

        if not payload.stop_respected:
            discipline -= 35
            flags.append("stop-discipline-breach")
            actions.append("enforce immutable initial risk and stop governance")
        else:
            strengths.append("stop discipline respected")

        if not payload.target_plan_respected:
            discipline -= 20
            flags.append("target-plan-deviation")
            actions.append("define partial and final exits before entry")
        else:
            strengths.append("target plan respected")

        if payload.news_risk_present:
            discipline -= 10
            flags.append("news-risk-present")
            actions.append("review event-risk timing and exposure")

        execution_quality = max(0.0, min(100.0, discipline * 0.7 + payload.confidence_score * 0.3))
        risk_efficiency = max(0.0, min(100.0, 50.0 + payload.realized_r_multiple * 12.5))

        return JournalAnalytics(
            outcome=outcome,
            execution_quality_score=round(execution_quality, 2),
            discipline_score=round(max(0.0, discipline), 2),
            risk_efficiency_score=round(risk_efficiency, 2),
            expectancy_contribution=round(payload.realized_r_multiple, 4),
            process_flags=flags,
            strengths=strengths,
            improvement_actions=actions,
        )

    def _append_audit(
        self,
        record: TradeJournalRecord,
        action: str,
        actor: str,
        from_state: Optional[JournalState],
        to_state: JournalState,
        details: Optional[Dict[str, object]] = None,
    ) -> None:
        self._audit.append(
            AuditEvent(
                workspace_id=record.workspace_id,
                record_id=record.id,
                action=action,
                actor=actor,
                from_state=from_state,
                to_state=to_state,
                details=details or {},
            )
        )
