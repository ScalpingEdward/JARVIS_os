from datetime import datetime, timezone
from uuid import UUID

from .models import (
    InstitutionalTradeJournalAudit,
    InstitutionalTradeJournalCreate,
    InstitutionalTradeJournalRecord,
    InstitutionalTradeJournalStatus,
    ReplayCheckpoint,
    TradeJournalExecuteRequest,
    TradeJournalState,
)


class InstitutionalTradeJournalService:
    def __init__(self) -> None:
        self._records: dict[UUID, InstitutionalTradeJournalRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[InstitutionalTradeJournalAudit] = []

    def create(self, payload: InstitutionalTradeJournalCreate) -> InstitutionalTradeJournalRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail, metrics, replay, lesson = self._evaluate(payload)
        record = InstitutionalTradeJournalRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            replay=replay,
            lesson=lesson,
            **metrics,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: InstitutionalTradeJournalCreate):
        trade = payload.trade
        empty = self._empty_metrics()
        if payload.upstream_risk_brain_blocked:
            return TradeJournalState.BLOCKED, "upstream Risk Brain hard block", empty, [], ""
        if not payload.account_risk_approved or not payload.prop_rules_approved:
            return TradeJournalState.BLOCKED, "account-risk and prop-rule approval required", empty, [], ""
        if not (trade.routed_by_v19_06 and trade.market_allowed_by_v19_08 and trade.shadow_validated_by_v19_09):
            return TradeJournalState.EVIDENCE_REQUIRED, "v19.06, v19.08 and v19.09 evidence required", empty, [], ""

        setup = min(100.0, trade.signal_confidence * 0.45 + trade.market_score * 0.45 + min(trade.planned_rr, 5) * 2)
        execution = max(0.0, 100 - trade.slippage_bps * 4 - min(trade.mae_r, 3) * 8)
        management = max(0.0, min(100.0, 50 + trade.mfe_r * 15 + trade.realized_rr * 10))
        discipline = 100.0
        if abs(trade.pnl / trade.risk_amount - trade.realized_rr) > 0.25:
            discipline -= 20
        if trade.holding_seconds == 0:
            discipline -= 20
        process = round(setup * 0.35 + execution * 0.25 + management * 0.2 + discipline * 0.2, 2)

        if trade.pnl > 0 and process >= 75:
            outcome = "good-process-good-outcome"
            lesson = "Retain the setup and execution pattern; preserve the same risk discipline."
        elif trade.pnl <= 0 and process >= 75:
            outcome = "good-process-bad-outcome"
            lesson = "Accept the loss as valid variance; do not weaken a compliant process."
        elif trade.pnl > 0:
            outcome = "bad-process-good-outcome"
            lesson = "Do not reward the profit; correct the process defects before repetition."
        else:
            outcome = "bad-process-bad-outcome"
            lesson = "Suspend this execution pattern until the identified process defects are corrected."

        replay = [
            ReplayCheckpoint(name="signal", expected_action="validate routed signal", evidence=f"confidence={trade.signal_confidence}", passed=trade.signal_confidence >= 50),
            ReplayCheckpoint(name="market", expected_action="confirm market permission", evidence=f"market_score={trade.market_score}", passed=trade.market_allowed_by_v19_08),
            ReplayCheckpoint(name="risk", expected_action="preserve approved risk", evidence=f"risk_amount={trade.risk_amount}", passed=payload.account_risk_approved),
            ReplayCheckpoint(name="execution", expected_action="control slippage and adverse excursion", evidence=f"slippage={trade.slippage_bps}, mae_r={trade.mae_r}", passed=execution >= 70),
            ReplayCheckpoint(name="management", expected_action="convert favorable excursion", evidence=f"mfe_r={trade.mfe_r}, realized_rr={trade.realized_rr}", passed=management >= 70),
        ]
        state = TradeJournalState.JOURNAL_PENDING if process >= 75 else TradeJournalState.REVIEW_REQUIRED
        detail = "institutional journal ready for completion" if state == TradeJournalState.JOURNAL_PENDING else "process defects require governed review"
        metrics = {
            "setup_quality_score": round(setup, 2),
            "execution_quality_score": round(execution, 2),
            "management_quality_score": round(management, 2),
            "discipline_score": round(discipline, 2),
            "process_score": process,
            "outcome_classification": outcome,
        }
        return state, detail, metrics, replay, lesson

    def execute(self, record_id: UUID, workspace_id: str, request: TradeJournalExecuteRequest) -> InstitutionalTradeJournalRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("journal record not found")
        approved = request.human_approved if request.human_approved is not None else record.request.human_approved
        if request.action in {"complete", "approve-lesson"} and not approved:
            raise ValueError("human approval required")
        if record.state in {TradeJournalState.BLOCKED, TradeJournalState.EVIDENCE_REQUIRED, TradeJournalState.INPUT_INVALID, TradeJournalState.FAILED}:
            raise ValueError("journal action unavailable from current state")
        if request.action == "complete":
            record.state, record.detail = TradeJournalState.JOURNAL_COMPLETE, "journal completed and replay evidence sealed"
        elif request.action == "approve-lesson":
            record.state, record.detail = TradeJournalState.LESSON_APPROVED, "trade lesson approved for downstream memory"
        elif request.action == "archive":
            record.state, record.detail = TradeJournalState.ARCHIVED, "journal archived"
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> InstitutionalTradeJournalRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[InstitutionalTradeJournalRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> InstitutionalTradeJournalStatus:
        records = self.list_records(workspace_id)
        complete = {TradeJournalState.JOURNAL_COMPLETE, TradeJournalState.LESSON_APPROVED, TradeJournalState.ARCHIVED}
        review = {TradeJournalState.REVIEW_REQUIRED, TradeJournalState.EVIDENCE_REQUIRED, TradeJournalState.BLOCKED}
        return InstitutionalTradeJournalStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            complete_records=sum(record.state in complete for record in records),
            review_records=sum(record.state in review for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[InstitutionalTradeJournalAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    @staticmethod
    def _empty_metrics() -> dict[str, float | str]:
        return {
            "setup_quality_score": 0,
            "execution_quality_score": 0,
            "management_quality_score": 0,
            "discipline_score": 0,
            "process_score": 0,
            "outcome_classification": "unclassified",
        }

    def _log(self, record: InstitutionalTradeJournalRecord, actor_id: str, action: str) -> None:
        self._audit.append(InstitutionalTradeJournalAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


institutional_trade_journal_service = InstitutionalTradeJournalService()
