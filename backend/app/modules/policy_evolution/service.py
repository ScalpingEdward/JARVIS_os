from __future__ import annotations

from datetime import datetime, timezone

from .models import AuditEvent, PolicyEvolutionActionRequest, PolicyEvolutionCreate, PolicyEvolutionRecord, PolicyEvolutionState, RiskDecision


class PolicyEvolutionError(RuntimeError):
    pass


class PolicyEvolutionService:
    def __init__(self) -> None:
        self._records: dict[str, PolicyEvolutionRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: PolicyEvolutionCreate) -> PolicyEvolutionRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise PolicyEvolutionError("duplicate source key")
        record = PolicyEvolutionRecord(**payload.model_dump())
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> PolicyEvolutionRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise PolicyEvolutionError("policy evolution record not found")
        return record

    def list(self, workspace_id: str) -> list[PolicyEvolutionRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: PolicyEvolutionActionRequest) -> PolicyEvolutionRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action
        if action == "prepare-evidence":
            self._require(record, PolicyEvolutionState.DRAFT)
            record.state = PolicyEvolutionState.BLOCKED if record.risk_decision == RiskDecision.BLOCK else PolicyEvolutionState.EVIDENCE_READY
        elif action == "evaluate":
            self._require(record, PolicyEvolutionState.EVIDENCE_READY)
            if any(item.confidence < record.minimum_confidence for item in record.changes):
                raise PolicyEvolutionError("policy change confidence below threshold")
            record.state = PolicyEvolutionState.EVALUATED
        elif action == "propose":
            self._require(record, PolicyEvolutionState.EVALUATED)
            known = {item.change_id for item in record.changes}
            if not request.change_ids or not set(request.change_ids).issubset(known):
                raise PolicyEvolutionError("known change_ids are required")
            record.selected_change_ids = list(dict.fromkeys(request.change_ids))
            record.state = PolicyEvolutionState.PROPOSED
        elif action == "request-review":
            self._require(record, PolicyEvolutionState.PROPOSED)
            record.state = PolicyEvolutionState.HUMAN_REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, PolicyEvolutionState.HUMAN_REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = PolicyEvolutionState.APPROVED
        elif action == "stage":
            self._require(record, PolicyEvolutionState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = PolicyEvolutionState.STAGED
        elif action == "start-canary":
            self._require(record, PolicyEvolutionState.STAGED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = PolicyEvolutionState.CANARY
        elif action == "record-validation":
            if record.state not in {PolicyEvolutionState.CANARY, PolicyEvolutionState.VALIDATING}:
                raise PolicyEvolutionError("validation is not active")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.validation_evidence_refs.extend(request.evidence_refs)
            if request.validation_healthy:
                record.consecutive_healthy_cycles += 1
                record.state = PolicyEvolutionState.VALIDATING
            else:
                record.consecutive_healthy_cycles = 0
                record.state = PolicyEvolutionState.ROLLED_BACK
        elif action == "promote":
            self._require(record, PolicyEvolutionState.VALIDATING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise PolicyEvolutionError("healthy validation cycles incomplete")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = PolicyEvolutionState.PROMOTED
        elif action == "rollback":
            if record.state not in {PolicyEvolutionState.STAGED, PolicyEvolutionState.CANARY, PolicyEvolutionState.VALIDATING, PolicyEvolutionState.PROMOTED}:
                raise PolicyEvolutionError("rollback not allowed")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = PolicyEvolutionState.ROLLED_BACK
        elif action == "reject":
            if record.state not in {PolicyEvolutionState.HUMAN_REVIEW_REQUIRED, PolicyEvolutionState.APPROVED}:
                raise PolicyEvolutionError("reject not allowed")
            record.state = PolicyEvolutionState.REJECTED
        elif action == "fail":
            record.state = PolicyEvolutionState.FAILED
        elif action == "archive":
            if record.state not in {PolicyEvolutionState.PROMOTED, PolicyEvolutionState.ROLLED_BACK, PolicyEvolutionState.REJECTED, PolicyEvolutionState.FAILED, PolicyEvolutionState.BLOCKED}:
                raise PolicyEvolutionError("record is not terminal")
            record.state = PolicyEvolutionState.ARCHIVED
        self._touch(record)
        self._emit(record, action, request.actor, before, record.state)
        return record

    @staticmethod
    def _require(record: PolicyEvolutionRecord, expected: PolicyEvolutionState) -> None:
        if record.state != expected:
            raise PolicyEvolutionError(f"expected state {expected.value}")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise PolicyEvolutionError(f"{label} is required")
        if value in store:
            raise PolicyEvolutionError(f"duplicate {label}")
        store.add(value)

    @staticmethod
    def _touch(record: PolicyEvolutionRecord) -> None:
        record.updated_at = datetime.now(timezone.utc)

    def _emit(self, record: PolicyEvolutionRecord, action: str, actor: str, before: PolicyEvolutionState | None, after: PolicyEvolutionState) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after))


service = PolicyEvolutionService()
