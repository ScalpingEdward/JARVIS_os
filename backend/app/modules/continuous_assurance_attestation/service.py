from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock

from .models import (
    AssuranceActionRequest,
    AssuranceAssessment,
    AssuranceAssessmentCreate,
    AssuranceBand,
    AssuranceState,
    AuditEvent,
    RiskDecision,
)


class ContinuousAssuranceError(ValueError):
    pass


class ContinuousAssuranceService:
    def __init__(self) -> None:
        self._records: dict[str, AssuranceAssessment] = {}
        self._sources: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipts: set[str] = set()
        self._attestation_digests: set[str] = set()
        self._audit: list[AuditEvent] = []
        self._lock = RLock()

    def status(self) -> dict[str, object]:
        return {"module": "continuous-assurance-attestation", "version": "21.33", "status": "ready", "records": len(self._records)}

    def create(self, payload: AssuranceAssessmentCreate) -> AssuranceAssessment:
        with self._lock:
            key = (payload.workspace_id, payload.source_key)
            if key in self._sources:
                raise ContinuousAssuranceError("duplicate source_key in workspace")
            state = AssuranceState.DRAFT
            if payload.risk_decision == RiskDecision.BLOCK:
                state = AssuranceState.BLOCKED
            elif not payload.trust_evidence_refs or not payload.runtime_evidence_refs:
                state = AssuranceState.EVIDENCE_REQUIRED
            record = AssuranceAssessment(**payload.model_dump(), state=state)
            self._records[record.record_id] = record
            self._sources.add(key)
            self._append_audit(record, "create", "system", None, state)
            return record.model_copy(deep=True)

    def list(self, workspace_id: str) -> list[AssuranceAssessment]:
        return [item.model_copy(deep=True) for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> AssuranceAssessment:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise ContinuousAssuranceError("assessment not found")
        return record.model_copy(deep=True)

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [item.model_copy(deep=True) for item in self._audit if item.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: AssuranceActionRequest) -> AssuranceAssessment:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.workspace_id != workspace_id:
                raise ContinuousAssuranceError("assessment not found")
            if record.risk_decision == RiskDecision.BLOCK and request.action not in {"fail", "archive"}:
                raise ContinuousAssuranceError("Risk Brain hard block is authoritative")
            before = record.state
            handler = getattr(self, f"_action_{request.action.replace('-', '_')}")
            handler(record, request)
            record.updated_at = datetime.now(timezone.utc)
            self._append_audit(record, request.action, request.actor, before, record.state, request)
            return record.model_copy(deep=True)

    def _action_evaluate(self, record: AssuranceAssessment, _: AssuranceActionRequest) -> None:
        self._require(record, AssuranceState.DRAFT)
        record.assurance_score = round(sum(item.weight for item in record.controls if item.compliant) * 100, 2)
        record.failed_control_count = sum(not item.compliant for item in record.controls)
        record.required_failure_count = sum(item.required and not item.compliant for item in record.controls)
        if record.required_failure_count:
            record.band = AssuranceBand.NON_COMPLIANT
        elif record.assurance_score < 70:
            record.band = AssuranceBand.WEAK
        elif record.assurance_score < 90:
            record.band = AssuranceBand.CONDITIONAL
        else:
            record.band = AssuranceBand.COMPLIANT
        record.state = AssuranceState.EVALUATED

    def _action_request_review(self, record: AssuranceAssessment, _: AssuranceActionRequest) -> None:
        self._require(record, AssuranceState.EVALUATED)
        record.state = AssuranceState.HUMAN_REVIEW_REQUIRED

    def _action_approve(self, record: AssuranceAssessment, request: AssuranceActionRequest) -> None:
        self._require(record, AssuranceState.HUMAN_REVIEW_REQUIRED)
        self._consume_token(request.approval_token)
        record.approval_actor = request.actor
        record.state = AssuranceState.APPROVED

    def _action_attest(self, record: AssuranceAssessment, request: AssuranceActionRequest) -> None:
        self._require(record, AssuranceState.APPROVED)
        if record.required_failure_count or record.assurance_score < 90:
            raise ContinuousAssuranceError("attestation requires compliant controls and score >= 90")
        digest = request.attestation_digest
        if not digest or len(digest) < 8:
            raise ContinuousAssuranceError("attestation_digest is required")
        if digest in self._attestation_digests:
            raise ContinuousAssuranceError("attestation digest replay detected")
        self._attestation_digests.add(digest)
        record.attestation_digest = digest
        record.band = AssuranceBand.ATTESTED
        record.state = AssuranceState.ATTESTED

    def _action_queue_remediation(self, record: AssuranceAssessment, request: AssuranceActionRequest) -> None:
        self._require(record, AssuranceState.APPROVED)
        if not record.remediations:
            raise ContinuousAssuranceError("no remediation controls defined")
        self._consume_receipt(request.receipt_id)
        record.state = AssuranceState.REMEDIATION_QUEUED

    def _action_complete_remediation(self, record: AssuranceAssessment, request: AssuranceActionRequest) -> None:
        self._require(record, AssuranceState.REMEDIATION_QUEUED)
        self._consume_receipt(request.receipt_id)
        expected = {item.remediation_id for item in record.remediations}
        applied = set(request.applied_remediation_ids)
        if applied != expected:
            raise ContinuousAssuranceError("all remediation controls must be applied exactly once")
        record.applied_remediation_ids = sorted(applied)
        record.state = AssuranceState.REMEDIATED

    def _action_verify(self, record: AssuranceAssessment, request: AssuranceActionRequest) -> None:
        self._require(record, AssuranceState.REMEDIATED)
        self._consume_receipt(request.receipt_id)
        if not request.verification_evidence_refs:
            raise ContinuousAssuranceError("verification evidence is required")
        record.verification_evidence_refs = request.verification_evidence_refs
        record.state = AssuranceState.VERIFIED

    def _action_reject(self, record: AssuranceAssessment, _: AssuranceActionRequest) -> None:
        self._require(record, AssuranceState.HUMAN_REVIEW_REQUIRED, AssuranceState.APPROVED)
        record.state = AssuranceState.REJECTED

    def _action_fail(self, record: AssuranceAssessment, _: AssuranceActionRequest) -> None:
        if record.state == AssuranceState.ARCHIVED:
            raise ContinuousAssuranceError("archived assessment cannot fail")
        record.state = AssuranceState.FAILED

    def _action_archive(self, record: AssuranceAssessment, _: AssuranceActionRequest) -> None:
        if record.state not in {AssuranceState.ATTESTED, AssuranceState.VERIFIED, AssuranceState.REJECTED, AssuranceState.FAILED, AssuranceState.BLOCKED}:
            raise ContinuousAssuranceError("assessment is not terminal")
        record.state = AssuranceState.ARCHIVED

    def _consume_token(self, token: str | None) -> None:
        if not token:
            raise ContinuousAssuranceError("approval_token is required")
        if token in self._approval_tokens:
            raise ContinuousAssuranceError("approval token replay detected")
        self._approval_tokens.add(token)

    def _consume_receipt(self, receipt: str | None) -> None:
        if not receipt:
            raise ContinuousAssuranceError("receipt_id is required")
        if receipt in self._receipts:
            raise ContinuousAssuranceError("receipt replay detected")
        self._receipts.add(receipt)

    @staticmethod
    def _require(record: AssuranceAssessment, *states: AssuranceState) -> None:
        if record.state not in states:
            expected = ", ".join(item.value for item in states)
            raise ContinuousAssuranceError(f"invalid state transition from {record.state.value}; expected {expected}")

    def _append_audit(self, record: AssuranceAssessment, action: str, actor: str, before: AssuranceState | None, after: AssuranceState, request: AssuranceActionRequest | None = None) -> None:
        details = {} if request is None else {"note": request.note, "receipt_id": request.receipt_id}
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, details=details))
