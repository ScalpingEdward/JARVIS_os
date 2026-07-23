from __future__ import annotations

from datetime import datetime, timezone

from .models import AuditEvent, CloseActionRequest, CloseState, FinancialCloseCreate, FinancialCloseRecord, RiskDecision, ValuationStatus


class FinancialCloseError(RuntimeError):
    pass


class FinancialCloseService:
    def __init__(self) -> None:
        self._records: dict[str, FinancialCloseRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: FinancialCloseCreate) -> FinancialCloseRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise FinancialCloseError("duplicate source key")
        record = FinancialCloseRecord(**payload.model_dump())
        record.calculated_nav = self._calculate_nav(record)
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> FinancialCloseRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise FinancialCloseError("financial close record not found")
        return record

    def list(self, workspace_id: str) -> list[FinancialCloseRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: CloseActionRequest) -> FinancialCloseRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, CloseState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = CloseState.BLOCKED
            elif not record.close_evidence_refs:
                raise FinancialCloseError("close evidence is required")
            else:
                record.state = CloseState.EVIDENCE_READY
        elif action == "calculate":
            self._require(record, CloseState.EVIDENCE_READY)
            stale = sum(item.valuation_status in {ValuationStatus.STALE, ValuationStatus.MISSING} for item in record.positions)
            if stale / len(record.positions) > record.maximum_stale_price_ratio:
                record.state = CloseState.ESCALATED
            else:
                record.calculated_nav = request.calculated_nav if request.calculated_nav is not None else self._calculate_nav(record)
                record.external_nav = request.external_nav
                record.nav_variance = self._variance(record.calculated_nav, record.external_nav)
                record.state = CloseState.ESCALATED if record.nav_variance > record.maximum_nav_variance else CloseState.CALCULATED
        elif action == "request-review":
            self._require(record, CloseState.CALCULATED)
            record.state = CloseState.REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, CloseState.REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = CloseState.APPROVED
        elif action == "close":
            self._require(record, CloseState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.verification_evidence_refs.extend(request.evidence_refs)
            record.state = CloseState.CLOSED
        elif action == "record-cycle":
            if record.state not in {CloseState.CLOSED, CloseState.MONITORING}:
                raise FinancialCloseError("close monitoring is not active")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.verification_evidence_refs.extend(request.evidence_refs)
            if request.external_nav is not None:
                record.external_nav = request.external_nav
                record.nav_variance = self._variance(record.calculated_nav, record.external_nav)
            healthy = bool(request.cycle_healthy) and record.nav_variance <= record.maximum_nav_variance
            record.consecutive_healthy_cycles = record.consecutive_healthy_cycles + 1 if healthy else 0
            record.state = CloseState.MONITORING if healthy else CloseState.ESCALATED
        elif action == "verify":
            self._require(record, CloseState.MONITORING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise FinancialCloseError("healthy verification cycles incomplete")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = CloseState.VERIFIED
        elif action == "escalate":
            if record.state in {CloseState.ARCHIVED, CloseState.REVOKED, CloseState.BLOCKED}:
                raise FinancialCloseError("escalation not allowed")
            record.state = CloseState.ESCALATED
        elif action == "reopen":
            if record.state not in {CloseState.CLOSED, CloseState.MONITORING, CloseState.VERIFIED, CloseState.ESCALATED}:
                raise FinancialCloseError("reopen not allowed")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.consecutive_healthy_cycles = 0
            record.state = CloseState.REOPENED
        elif action == "revoke":
            if record.state in {CloseState.ARCHIVED, CloseState.REVOKED}:
                raise FinancialCloseError("revocation not allowed")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = CloseState.REVOKED
        elif action == "archive":
            if record.state not in {CloseState.VERIFIED, CloseState.REVOKED}:
                raise FinancialCloseError("only verified or revoked records can be archived")
            record.state = CloseState.ARCHIVED

        record.updated_at = datetime.now(timezone.utc)
        self._emit(record, action, request.actor, before, record.state)
        return record

    @staticmethod
    def _calculate_nav(record: FinancialCloseRecord) -> float:
        return sum(item.market_value for item in record.positions) + record.cash_balance - record.liabilities - record.accrued_fees

    @staticmethod
    def _variance(internal: float, external: float | None) -> float:
        if external is None:
            return 0
        denominator = max(abs(external), 1e-9)
        return abs(internal - external) / denominator

    @staticmethod
    def _require(record: FinancialCloseRecord, state: CloseState) -> None:
        if record.state != state:
            raise FinancialCloseError(f"action requires state {state.value}")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise FinancialCloseError(f"{label} is required")
        if value in store:
            raise FinancialCloseError(f"{label} replay detected")
        store.add(value)

    def _emit(self, record: FinancialCloseRecord, action: str, actor: str, before: CloseState | None, after: CloseState) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after))


service = FinancialCloseService()
