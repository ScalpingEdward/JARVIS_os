from __future__ import annotations

from datetime import datetime, timezone

from .models import AuditEvent, RiskDecision, TreasuryActionRequest, TreasuryCreate, TreasuryGovernanceRecord, TreasuryState


class TreasuryGovernanceError(RuntimeError):
    pass


class TreasuryGovernanceService:
    def __init__(self) -> None:
        self._records: dict[str, TreasuryGovernanceRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: TreasuryCreate) -> TreasuryGovernanceRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise TreasuryGovernanceError("duplicate source key")
        record = TreasuryGovernanceRecord(**payload.model_dump())
        record.total_exposure = sum(item.available_balance + item.reserved_balance for item in record.accounts)
        available = sum(item.available_balance for item in record.accounts)
        record.liquidity_ratio = available / record.total_exposure if record.total_exposure else 1
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> TreasuryGovernanceRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise TreasuryGovernanceError("treasury governance record not found")
        return record

    def list(self, workspace_id: str) -> list[TreasuryGovernanceRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: TreasuryActionRequest) -> TreasuryGovernanceRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, TreasuryState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = TreasuryState.BLOCKED
            elif not record.treasury_evidence_refs:
                raise TreasuryGovernanceError("treasury evidence is required")
            else:
                record.state = TreasuryState.EVIDENCE_READY
        elif action == "evaluate":
            self._require(record, TreasuryState.EVIDENCE_READY)
            provider_totals: dict[str, float] = {}
            for account in record.accounts:
                exposure = account.available_balance + account.reserved_balance
                if exposure > account.maximum_exposure:
                    record.state = TreasuryState.ESCALATED
                    break
                provider_totals[account.provider_id] = provider_totals.get(account.provider_id, 0) + exposure
            else:
                total = sum(provider_totals.values())
                if total > record.maximum_total_exposure:
                    record.state = TreasuryState.ESCALATED
                elif total and any(amount / total > record.maximum_single_provider_weight for amount in provider_totals.values()):
                    record.state = TreasuryState.ESCALATED
                elif record.liquidity_ratio < record.minimum_liquidity_ratio:
                    record.state = TreasuryState.ESCALATED
                else:
                    record.state = TreasuryState.EVALUATED
        elif action == "propose-funding":
            self._require(record, TreasuryState.EVALUATED)
            known = {item.instruction_id: item for item in record.instructions}
            if not request.instruction_ids or not set(request.instruction_ids).issubset(known):
                raise TreasuryGovernanceError("known instruction_ids are required")
            if any(known[item].confidence < record.minimum_confidence for item in request.instruction_ids):
                raise TreasuryGovernanceError("funding confidence below threshold")
            record.selected_instruction_ids = list(dict.fromkeys(request.instruction_ids))
            record.state = TreasuryState.FUNDING_PROPOSED
        elif action == "request-review":
            self._require(record, TreasuryState.FUNDING_PROPOSED)
            record.state = TreasuryState.EXECUTIVE_REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, TreasuryState.EXECUTIVE_REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = TreasuryState.APPROVED
        elif action == "execute-funding":
            self._require(record, TreasuryState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.funding_evidence_refs.extend(request.evidence_refs)
            record.state = TreasuryState.FUNDED
        elif action == "record-cycle":
            if record.state not in {TreasuryState.FUNDED, TreasuryState.MONITORING}:
                raise TreasuryGovernanceError("treasury monitoring is not active")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            if request.liquidity_ratio is not None:
                record.liquidity_ratio = request.liquidity_ratio
            if request.total_exposure is not None:
                record.total_exposure = request.total_exposure
            record.funding_evidence_refs.extend(request.evidence_refs)
            if record.total_exposure > record.maximum_total_exposure or record.liquidity_ratio < record.minimum_liquidity_ratio:
                record.consecutive_healthy_cycles = 0
                record.state = TreasuryState.ESCALATED
            elif request.cycle_healthy:
                record.consecutive_healthy_cycles += 1
                record.state = TreasuryState.MONITORING
            else:
                record.consecutive_healthy_cycles = 0
                record.state = TreasuryState.MONITORING
        elif action == "confirm-liquid":
            self._require(record, TreasuryState.MONITORING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise TreasuryGovernanceError("required healthy cycles incomplete")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = TreasuryState.LIQUID
        elif action == "escalate":
            if record.state in {TreasuryState.ARCHIVED, TreasuryState.REVOKED, TreasuryState.BLOCKED}:
                raise TreasuryGovernanceError("escalation not allowed")
            record.state = TreasuryState.ESCALATED
        elif action == "suspend":
            if record.state not in {TreasuryState.APPROVED, TreasuryState.FUNDED, TreasuryState.MONITORING, TreasuryState.ESCALATED}:
                raise TreasuryGovernanceError("suspension not allowed")
            record.state = TreasuryState.SUSPENDED
        elif action == "resume":
            self._require(record, TreasuryState.SUSPENDED)
            record.state = TreasuryState.MONITORING if record.funding_evidence_refs else TreasuryState.APPROVED
        elif action == "revoke":
            if record.state in {TreasuryState.ARCHIVED, TreasuryState.REVOKED, TreasuryState.BLOCKED}:
                raise TreasuryGovernanceError("revocation not allowed")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = TreasuryState.REVOKED
        elif action == "archive":
            if record.state not in {TreasuryState.LIQUID, TreasuryState.ESCALATED, TreasuryState.REVOKED}:
                raise TreasuryGovernanceError("archive not allowed")
            record.state = TreasuryState.ARCHIVED
        else:
            raise TreasuryGovernanceError("unsupported action")

        self._touch(record)
        self._emit(record, action, request.actor, before, record.state, {"note": request.note})
        return record

    def _require(self, record: TreasuryGovernanceRecord, expected: TreasuryState) -> None:
        if record.state != expected:
            raise TreasuryGovernanceError(f"action requires state {expected.value}")

    def _consume(self, store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise TreasuryGovernanceError(f"{label} is required")
        if value in store:
            raise TreasuryGovernanceError(f"{label} replay detected")
        store.add(value)

    def _touch(self, record: TreasuryGovernanceRecord) -> None:
        record.updated_at = datetime.now(timezone.utc)

    def _emit(self, record: TreasuryGovernanceRecord, action: str, actor: str, before: TreasuryState | None, after: TreasuryState, details: dict | None = None) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, details=details or {}))


service = TreasuryGovernanceService()
