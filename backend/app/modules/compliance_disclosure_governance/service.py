from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AuditEvent,
    ComplianceActionRequest,
    ComplianceCreate,
    ComplianceGovernanceRecord,
    ComplianceState,
    ObligationStatus,
    RiskDecision,
)


class ComplianceGovernanceError(RuntimeError):
    pass


class ComplianceGovernanceService:
    def __init__(self) -> None:
        self._records: dict[str, ComplianceGovernanceRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: ComplianceCreate) -> ComplianceGovernanceRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ComplianceGovernanceError("duplicate source key")
        record = ComplianceGovernanceRecord(**payload.model_dump())
        record.open_obligations = self._open_obligations(record)
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> ComplianceGovernanceRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise ComplianceGovernanceError("compliance governance record not found")
        return record

    def list(self, workspace_id: str) -> list[ComplianceGovernanceRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: ComplianceActionRequest) -> ComplianceGovernanceRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, ComplianceState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = ComplianceState.BLOCKED
            elif not record.compliance_evidence_refs:
                raise ComplianceGovernanceError("compliance evidence is required")
            else:
                record.state = ComplianceState.EVIDENCE_READY
        elif action == "assess":
            self._require(record, ComplianceState.EVIDENCE_READY)
            record.open_obligations = self._open_obligations(record)
            breached = any(item.status == ObligationStatus.BREACHED for item in record.obligations)
            record.state = ComplianceState.ESCALATED if breached or record.open_obligations > record.maximum_open_obligations else ComplianceState.ASSESSED
        elif action == "prepare-disclosure":
            self._require(record, ComplianceState.ASSESSED)
            if any(item.confidence < record.minimum_disclosure_confidence for item in record.disclosures):
                raise ComplianceGovernanceError("disclosure confidence below threshold")
            record.state = ComplianceState.DISCLOSURE_PREPARED
        elif action == "request-review":
            self._require(record, ComplianceState.DISCLOSURE_PREPARED)
            record.state = ComplianceState.REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, ComplianceState.REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = ComplianceState.APPROVED
        elif action == "file":
            self._require(record, ComplianceState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.filing_evidence_refs.extend(request.evidence_refs)
            record.state = ComplianceState.FILED
        elif action == "record-cycle":
            if record.state not in {ComplianceState.FILED, ComplianceState.MONITORING}:
                raise ComplianceGovernanceError("compliance monitoring is not active")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.filing_evidence_refs.extend(request.evidence_refs)
            if request.observed_open_obligations is not None:
                record.open_obligations = request.observed_open_obligations
            healthy = bool(request.cycle_healthy) and record.open_obligations <= record.maximum_open_obligations
            record.consecutive_healthy_cycles = record.consecutive_healthy_cycles + 1 if healthy else 0
            record.state = ComplianceState.MONITORING if healthy else ComplianceState.ESCALATED
        elif action == "verify":
            self._require(record, ComplianceState.MONITORING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise ComplianceGovernanceError("required healthy cycles incomplete")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = ComplianceState.VERIFIED
        elif action == "escalate":
            if record.state in {ComplianceState.ARCHIVED, ComplianceState.REVOKED, ComplianceState.BLOCKED}:
                raise ComplianceGovernanceError("escalation not allowed")
            record.state = ComplianceState.ESCALATED
        elif action == "suspend":
            if record.state not in {ComplianceState.FILED, ComplianceState.MONITORING, ComplianceState.ESCALATED}:
                raise ComplianceGovernanceError("suspension not allowed")
            record.state = ComplianceState.SUSPENDED
        elif action == "resume":
            self._require(record, ComplianceState.SUSPENDED)
            record.state = ComplianceState.MONITORING
        elif action == "revoke":
            if record.state in {ComplianceState.ARCHIVED, ComplianceState.REVOKED}:
                raise ComplianceGovernanceError("revocation not allowed")
            record.state = ComplianceState.REVOKED
        elif action == "archive":
            if record.state not in {ComplianceState.VERIFIED, ComplianceState.REVOKED}:
                raise ComplianceGovernanceError("archive not allowed")
            record.state = ComplianceState.ARCHIVED
        else:
            raise ComplianceGovernanceError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._emit(record, action, request.actor, before, record.state, request.model_dump(exclude_none=True))
        return record

    @staticmethod
    def _open_obligations(record: ComplianceGovernanceRecord) -> int:
        return sum(item.status == ObligationStatus.OPEN for item in record.obligations)

    @staticmethod
    def _require(record: ComplianceGovernanceRecord, state: ComplianceState) -> None:
        if record.state != state:
            raise ComplianceGovernanceError(f"action requires state {state.value}")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise ComplianceGovernanceError(f"{label} is required")
        if value in store:
            raise ComplianceGovernanceError(f"{label} already consumed")
        store.add(value)

    def _emit(self, record: ComplianceGovernanceRecord, action: str, actor: str, before: ComplianceState | None, after: ComplianceState, details: dict | None = None) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, details=details or {}))


service = ComplianceGovernanceService()
