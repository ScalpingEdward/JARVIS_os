from __future__ import annotations

from datetime import datetime, timezone

from .models import AuditEvent, ReportingActionRequest, ReportingCreate, ReportingGovernanceRecord, ReportingState, RiskDecision


class ReportingGovernanceError(RuntimeError):
    pass


class ReportingGovernanceService:
    def __init__(self) -> None:
        self._records: dict[str, ReportingGovernanceRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: ReportingCreate) -> ReportingGovernanceRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ReportingGovernanceError("duplicate source key")
        record = ReportingGovernanceRecord(**payload.model_dump())
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> ReportingGovernanceRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise ReportingGovernanceError("reporting governance record not found")
        return record

    def list(self, workspace_id: str) -> list[ReportingGovernanceRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: ReportingActionRequest) -> ReportingGovernanceRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, ReportingState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = ReportingState.BLOCKED
            elif not record.reporting_evidence_refs:
                raise ReportingGovernanceError("reporting evidence is required")
            else:
                record.state = ReportingState.EVIDENCE_READY
        elif action == "calculate-attribution":
            self._require(record, ReportingState.EVIDENCE_READY)
            if any(item.risk_contribution > record.maximum_risk_contribution for item in record.attribution_components):
                record.state = ReportingState.ESCALATED
            else:
                record.attributed_return = sum(item.contribution - item.fees for item in record.attribution_components)
                record.attribution_variance = abs(record.attributed_return - record.total_return)
                record.state = ReportingState.ESCALATED if record.attribution_variance > record.maximum_attribution_variance else ReportingState.ATTRIBUTED
        elif action == "generate-report":
            self._require(record, ReportingState.ATTRIBUTED)
            if any(item.confidence < record.minimum_section_confidence for item in record.sections):
                raise ReportingGovernanceError("report section confidence below threshold")
            record.state = ReportingState.REPORT_GENERATED
        elif action == "request-review":
            self._require(record, ReportingState.REPORT_GENERATED)
            record.state = ReportingState.REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, ReportingState.REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = ReportingState.APPROVED
        elif action == "publish":
            self._require(record, ReportingState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.publication_evidence_refs.extend(request.evidence_refs)
            record.state = ReportingState.PUBLISHED
        elif action == "record-cycle":
            if record.state not in {ReportingState.PUBLISHED, ReportingState.MONITORING}:
                raise ReportingGovernanceError("report monitoring is not active")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.publication_evidence_refs.extend(request.evidence_refs)
            observed = request.observed_total_return if request.observed_total_return is not None else record.total_return
            healthy = bool(request.cycle_healthy) and abs(observed - record.attributed_return) <= record.maximum_attribution_variance
            record.consecutive_healthy_cycles = record.consecutive_healthy_cycles + 1 if healthy else 0
            record.state = ReportingState.MONITORING if healthy else ReportingState.ESCALATED
        elif action == "verify":
            self._require(record, ReportingState.MONITORING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise ReportingGovernanceError("required healthy cycles incomplete")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = ReportingState.VERIFIED
        elif action == "escalate":
            if record.state in {ReportingState.ARCHIVED, ReportingState.REVOKED, ReportingState.BLOCKED}:
                raise ReportingGovernanceError("escalation not allowed")
            record.state = ReportingState.ESCALATED
        elif action == "suspend":
            if record.state not in {ReportingState.APPROVED, ReportingState.PUBLISHED, ReportingState.MONITORING, ReportingState.ESCALATED}:
                raise ReportingGovernanceError("suspension not allowed")
            record.state = ReportingState.SUSPENDED
        elif action == "resume":
            self._require(record, ReportingState.SUSPENDED)
            record.state = ReportingState.MONITORING if record.publication_evidence_refs else ReportingState.APPROVED
        elif action == "revoke":
            if record.state in {ReportingState.ARCHIVED, ReportingState.REVOKED}:
                raise ReportingGovernanceError("revocation not allowed")
            record.state = ReportingState.REVOKED
        elif action == "archive":
            if record.state not in {ReportingState.VERIFIED, ReportingState.REVOKED, ReportingState.ESCALATED}:
                raise ReportingGovernanceError("archive not allowed")
            record.state = ReportingState.ARCHIVED
        else:
            raise ReportingGovernanceError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._emit(record, action, request.actor, before, record.state, request.note)
        return record

    @staticmethod
    def _require(record: ReportingGovernanceRecord, expected: ReportingState) -> None:
        if record.state != expected:
            raise ReportingGovernanceError(f"action requires state {expected.value}")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise ReportingGovernanceError(f"{label} is required")
        if value in store:
            raise ReportingGovernanceError(f"{label} already consumed")
        store.add(value)

    def _emit(self, record: ReportingGovernanceRecord, action: str, actor: str, before: ReportingState | None, after: ReportingState, note: str | None = None) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, details={"note": note} if note else {}))


service = ReportingGovernanceService()
