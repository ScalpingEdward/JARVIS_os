from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AuditEvent,
    InitiativeStatus,
    MaturityActionRequest,
    MaturityCreate,
    MaturityGovernanceRecord,
    MaturityState,
    RiskDecision,
)


class MaturityGovernanceError(RuntimeError):
    pass


class MaturityGovernanceService:
    def __init__(self) -> None:
        self._records: dict[str, MaturityGovernanceRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: MaturityCreate) -> MaturityGovernanceRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise MaturityGovernanceError("duplicate source key")
        record = MaturityGovernanceRecord(**payload.model_dump())
        self._refresh(record)
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> MaturityGovernanceRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise MaturityGovernanceError("maturity governance record not found")
        return record

    def list(self, workspace_id: str) -> list[MaturityGovernanceRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: MaturityActionRequest) -> MaturityGovernanceRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, MaturityState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = MaturityState.BLOCKED
            elif not record.maturity_evidence_refs:
                raise MaturityGovernanceError("maturity evidence is required")
            else:
                record.state = MaturityState.EVIDENCE_READY
        elif action == "assess":
            self._require(record, MaturityState.EVIDENCE_READY)
            self._refresh(record)
            breached = (
                record.average_maturity < record.minimum_average_maturity
                or record.below_minimum_domains > record.maximum_below_minimum_domains
                or record.failed_initiatives > record.maximum_failed_initiatives
            )
            record.state = MaturityState.ESCALATED if breached else MaturityState.ASSESSED
        elif action == "prepare-improvement-plan":
            self._require(record, MaturityState.ASSESSED)
            if any(item.confidence < record.minimum_initiative_confidence for item in record.initiatives):
                raise MaturityGovernanceError("initiative confidence below threshold")
            record.state = MaturityState.IMPROVEMENT_PLAN_READY
        elif action == "request-review":
            self._require(record, MaturityState.IMPROVEMENT_PLAN_READY)
            record.state = MaturityState.REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, MaturityState.REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = MaturityState.APPROVED
        elif action == "implement":
            self._require(record, MaturityState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.implementation_evidence_refs.extend(request.evidence_refs)
            record.state = MaturityState.IMPLEMENTING
        elif action == "record-cycle":
            if record.state not in {MaturityState.IMPLEMENTING, MaturityState.MONITORING}:
                raise MaturityGovernanceError("improvement monitoring is not active")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.implementation_evidence_refs.extend(request.evidence_refs)
            if request.observed_average_maturity is not None:
                record.average_maturity = request.observed_average_maturity
            if request.observed_below_minimum_domains is not None:
                record.below_minimum_domains = request.observed_below_minimum_domains
            if request.observed_failed_initiatives is not None:
                record.failed_initiatives = request.observed_failed_initiatives
            healthy = (
                bool(request.cycle_healthy)
                and record.average_maturity >= record.minimum_average_maturity
                and record.below_minimum_domains <= record.maximum_below_minimum_domains
                and record.failed_initiatives <= record.maximum_failed_initiatives
            )
            record.consecutive_healthy_cycles = record.consecutive_healthy_cycles + 1 if healthy else 0
            record.state = MaturityState.MONITORING if healthy else MaturityState.ESCALATED
        elif action == "verify":
            self._require(record, MaturityState.MONITORING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise MaturityGovernanceError("insufficient healthy monitoring cycles")
            record.state = MaturityState.VERIFIED
        elif action == "escalate":
            if record.state in {MaturityState.ARCHIVED, MaturityState.REVOKED}:
                raise MaturityGovernanceError("record cannot be escalated")
            record.state = MaturityState.ESCALATED
        elif action == "suspend":
            if record.state in {MaturityState.ARCHIVED, MaturityState.REVOKED, MaturityState.BLOCKED}:
                raise MaturityGovernanceError("record cannot be suspended")
            record.state = MaturityState.SUSPENDED
        elif action == "resume":
            self._require(record, MaturityState.SUSPENDED)
            record.state = MaturityState.MONITORING
        elif action == "revoke":
            if record.state == MaturityState.ARCHIVED:
                raise MaturityGovernanceError("archived record cannot be revoked")
            record.state = MaturityState.REVOKED
        elif action == "archive":
            if record.state not in {MaturityState.VERIFIED, MaturityState.REVOKED, MaturityState.ESCALATED}:
                raise MaturityGovernanceError("record is not eligible for archive")
            record.state = MaturityState.ARCHIVED
        else:
            raise MaturityGovernanceError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._emit(record, action, request.actor, before, record.state, request.note)
        return record

    def _refresh(self, record: MaturityGovernanceRecord) -> None:
        record.average_maturity = sum(item.current_score for item in record.domains) / len(record.domains)
        record.below_minimum_domains = sum(item.current_score < item.minimum_acceptable_score for item in record.domains)
        record.failed_initiatives = sum(item.status == InitiativeStatus.FAILED for item in record.initiatives)

    @staticmethod
    def _require(record: MaturityGovernanceRecord, state: MaturityState) -> None:
        if record.state != state:
            raise MaturityGovernanceError(f"action requires state {state.value}")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise MaturityGovernanceError(f"{label} is required")
        if value in store:
            raise MaturityGovernanceError(f"{label} replay detected")
        store.add(value)

    def _emit(
        self,
        record: MaturityGovernanceRecord,
        action: str,
        actor: str,
        before: MaturityState | None,
        after: MaturityState,
        note: str | None = None,
    ) -> None:
        self._audit.append(
            AuditEvent(
                record_id=record.record_id,
                workspace_id=record.workspace_id,
                action=action,
                actor=actor,
                from_state=before,
                to_state=after,
                details={"note": note} if note else {},
            )
        )


service = MaturityGovernanceService()
