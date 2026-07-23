from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AssuranceActionRequest,
    AssuranceCreate,
    AssuranceGovernanceRecord,
    AssuranceState,
    AuditEvent,
    ControlStatus,
    RiskDecision,
)


class AssuranceGovernanceError(RuntimeError):
    pass


class AssuranceGovernanceService:
    def __init__(self) -> None:
        self._records: dict[str, AssuranceGovernanceRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: AssuranceCreate) -> AssuranceGovernanceRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise AssuranceGovernanceError("duplicate source key")
        record = AssuranceGovernanceRecord(**payload.model_dump())
        self._refresh_counts(record)
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> AssuranceGovernanceRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise AssuranceGovernanceError("assurance governance record not found")
        return record

    def list(self, workspace_id: str) -> list[AssuranceGovernanceRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: AssuranceActionRequest) -> AssuranceGovernanceRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, AssuranceState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = AssuranceState.BLOCKED
            elif not record.assurance_evidence_refs:
                raise AssuranceGovernanceError("assurance evidence is required")
            else:
                record.state = AssuranceState.EVIDENCE_READY
        elif action == "assess":
            self._require(record, AssuranceState.EVIDENCE_READY)
            self._refresh_counts(record)
            severe = any(item.severity > record.maximum_control_severity for item in record.controls)
            if severe or record.deficient_controls > record.maximum_deficient_controls or record.failed_controls > record.maximum_failed_controls:
                record.state = AssuranceState.ESCALATED
            else:
                record.state = AssuranceState.ASSESSED
        elif action == "start-testing":
            self._require(record, AssuranceState.ASSESSED)
            if any(item.status == ControlStatus.NOT_TESTED for item in record.controls):
                raise AssuranceGovernanceError("all controls must be tested")
            if any(item.confidence < record.minimum_assertion_confidence for item in record.assertions):
                raise AssuranceGovernanceError("assertion confidence below threshold")
            record.state = AssuranceState.TESTING
        elif action == "request-review":
            self._require(record, AssuranceState.TESTING)
            record.state = AssuranceState.REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, AssuranceState.REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = AssuranceState.APPROVED
        elif action == "certify":
            self._require(record, AssuranceState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.certification_evidence_refs.extend(request.evidence_refs)
            record.state = AssuranceState.CERTIFIED
        elif action == "record-cycle":
            if record.state not in {AssuranceState.CERTIFIED, AssuranceState.MONITORING}:
                raise AssuranceGovernanceError("assurance monitoring is not active")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.certification_evidence_refs.extend(request.evidence_refs)
            if request.observed_deficient_controls is not None:
                record.deficient_controls = request.observed_deficient_controls
            if request.observed_failed_controls is not None:
                record.failed_controls = request.observed_failed_controls
            healthy = bool(request.cycle_healthy) and record.deficient_controls <= record.maximum_deficient_controls and record.failed_controls <= record.maximum_failed_controls
            record.consecutive_healthy_cycles = record.consecutive_healthy_cycles + 1 if healthy else 0
            record.state = AssuranceState.MONITORING if healthy else AssuranceState.ESCALATED
        elif action == "verify":
            self._require(record, AssuranceState.MONITORING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise AssuranceGovernanceError("required healthy cycles incomplete")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = AssuranceState.VERIFIED
        elif action == "escalate":
            if record.state in {AssuranceState.ARCHIVED, AssuranceState.REVOKED, AssuranceState.BLOCKED}:
                raise AssuranceGovernanceError("escalation not allowed")
            record.state = AssuranceState.ESCALATED
        elif action == "suspend":
            if record.state not in {AssuranceState.CERTIFIED, AssuranceState.MONITORING, AssuranceState.ESCALATED}:
                raise AssuranceGovernanceError("suspension not allowed")
            record.state = AssuranceState.SUSPENDED
        elif action == "resume":
            self._require(record, AssuranceState.SUSPENDED)
            record.state = AssuranceState.MONITORING if record.certification_evidence_refs else AssuranceState.APPROVED
        elif action == "revoke":
            if record.state in {AssuranceState.ARCHIVED, AssuranceState.REVOKED}:
                raise AssuranceGovernanceError("revocation not allowed")
            record.state = AssuranceState.REVOKED
        elif action == "archive":
            if record.state not in {AssuranceState.VERIFIED, AssuranceState.REVOKED, AssuranceState.ESCALATED}:
                raise AssuranceGovernanceError("archive not allowed")
            record.state = AssuranceState.ARCHIVED
        else:
            raise AssuranceGovernanceError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._emit(record, action, request.actor, before, record.state)
        return record

    @staticmethod
    def _refresh_counts(record: AssuranceGovernanceRecord) -> None:
        record.deficient_controls = sum(item.status == ControlStatus.DEFICIENT for item in record.controls)
        record.failed_controls = sum(item.status == ControlStatus.FAILED for item in record.controls)

    @staticmethod
    def _require(record: AssuranceGovernanceRecord, state: AssuranceState) -> None:
        if record.state != state:
            raise AssuranceGovernanceError(f"action requires state {state.value}")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise AssuranceGovernanceError(f"{label} is required")
        if value in store:
            raise AssuranceGovernanceError(f"{label} already consumed")
        store.add(value)

    def _emit(self, record: AssuranceGovernanceRecord, action: str, actor: str, before: AssuranceState | None, after: AssuranceState) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after))


service = AssuranceGovernanceService()
