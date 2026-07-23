from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AuditEvent,
    CandidateStatus,
    RiskDecision,
    StrategyFactoryActionRequest,
    StrategyFactoryCreate,
    StrategyFactoryRecord,
    StrategyFactoryState,
)


class StrategyFactoryError(RuntimeError):
    pass


class StrategyFactoryService:
    def __init__(self) -> None:
        self._records: dict[str, StrategyFactoryRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: StrategyFactoryCreate) -> StrategyFactoryRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise StrategyFactoryError("duplicate source key")
        record = StrategyFactoryRecord(**payload.model_dump())
        self._refresh(record)
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> StrategyFactoryRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise StrategyFactoryError("strategy factory record not found")
        return record

    def list(self, workspace_id: str) -> list[StrategyFactoryRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(
        self,
        record_id: str,
        workspace_id: str,
        request: StrategyFactoryActionRequest,
    ) -> StrategyFactoryRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, StrategyFactoryState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = StrategyFactoryState.BLOCKED
            elif not record.research_evidence_refs:
                raise StrategyFactoryError("research evidence is required")
            else:
                record.state = StrategyFactoryState.EVIDENCE_READY

        elif action == "research":
            self._require(record, StrategyFactoryState.EVIDENCE_READY)
            self._refresh(record)
            selected = self._selected(record)
            selected.status = CandidateStatus.RESEARCHED
            breached = (
                record.selected_confidence < record.minimum_candidate_confidence
                or record.selected_robustness < record.minimum_robustness_score
                or record.selected_drawdown > record.maximum_allowed_drawdown
            )
            record.state = StrategyFactoryState.ESCALATED if breached else StrategyFactoryState.RESEARCHED

        elif action == "prepare-validation":
            self._require(record, StrategyFactoryState.RESEARCHED)
            self._refresh(record)
            if record.validation_pass_rate < record.minimum_validation_pass_rate:
                raise StrategyFactoryError("validation pass rate below threshold")
            self._selected(record).status = CandidateStatus.VALIDATED
            record.state = StrategyFactoryState.VALIDATION_READY

        elif action == "request-review":
            self._require(record, StrategyFactoryState.VALIDATION_READY)
            record.state = StrategyFactoryState.REVIEW_REQUIRED

        elif action == "approve":
            self._require(record, StrategyFactoryState.REVIEW_REQUIRED)
            if not request.approval_token:
                raise StrategyFactoryError("approval token is required")
            if request.approval_token in self._approval_tokens:
                raise StrategyFactoryError("approval token already used")
            self._approval_tokens.add(request.approval_token)
            record.approval_actor = request.actor
            record.state = StrategyFactoryState.APPROVED

        elif action == "incubate":
            self._require(record, StrategyFactoryState.APPROVED)
            if not request.receipt_id:
                raise StrategyFactoryError("incubation receipt is required")
            if request.receipt_id in self._receipt_ids:
                raise StrategyFactoryError("incubation receipt already used")
            if not request.evidence_refs:
                raise StrategyFactoryError("incubation evidence is required")
            self._receipt_ids.add(request.receipt_id)
            record.incubation_evidence_refs.extend(request.evidence_refs)
            self._selected(record).status = CandidateStatus.INCUBATING
            record.state = StrategyFactoryState.INCUBATING

        elif action == "record-cycle":
            if record.state not in {StrategyFactoryState.INCUBATING, StrategyFactoryState.MONITORING}:
                raise StrategyFactoryError("record-cycle requires incubating or monitoring state")
            if request.cycle_healthy is None:
                raise StrategyFactoryError("cycle_healthy is required")
            if request.observed_drawdown is None or request.observed_robustness is None:
                raise StrategyFactoryError("observed drawdown and robustness are required")
            healthy = (
                request.cycle_healthy
                and request.observed_drawdown <= record.maximum_allowed_drawdown
                and request.observed_robustness >= record.minimum_robustness_score
            )
            if healthy:
                record.consecutive_healthy_cycles += 1
                record.state = StrategyFactoryState.MONITORING
            else:
                record.consecutive_healthy_cycles = 0
                record.state = StrategyFactoryState.ESCALATED
            if request.evidence_refs:
                record.incubation_evidence_refs.extend(request.evidence_refs)

        elif action == "promote":
            self._require(record, StrategyFactoryState.MONITORING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise StrategyFactoryError("insufficient healthy monitoring cycles")
            self._selected(record).status = CandidateStatus.PROMOTED
            record.state = StrategyFactoryState.PROMOTED

        elif action == "escalate":
            if record.state in {StrategyFactoryState.ARCHIVED, StrategyFactoryState.REVOKED}:
                raise StrategyFactoryError("terminal record cannot be escalated")
            record.state = StrategyFactoryState.ESCALATED

        elif action == "suspend":
            if record.state not in {
                StrategyFactoryState.APPROVED,
                StrategyFactoryState.INCUBATING,
                StrategyFactoryState.MONITORING,
                StrategyFactoryState.PROMOTED,
                StrategyFactoryState.ESCALATED,
            }:
                raise StrategyFactoryError("record cannot be suspended from current state")
            record.state = StrategyFactoryState.SUSPENDED

        elif action == "resume":
            self._require(record, StrategyFactoryState.SUSPENDED)
            record.state = StrategyFactoryState.MONITORING

        elif action == "retire":
            if record.state not in {StrategyFactoryState.PROMOTED, StrategyFactoryState.MONITORING}:
                raise StrategyFactoryError("only active strategies can be retired")
            self._selected(record).status = CandidateStatus.RETIRED
            record.state = StrategyFactoryState.RETIRED

        elif action == "revoke":
            if record.state == StrategyFactoryState.ARCHIVED:
                raise StrategyFactoryError("archived record cannot be revoked")
            record.state = StrategyFactoryState.REVOKED

        elif action == "archive":
            if record.state not in {
                StrategyFactoryState.PROMOTED,
                StrategyFactoryState.RETIRED,
                StrategyFactoryState.REVOKED,
                StrategyFactoryState.ESCALATED,
            }:
                raise StrategyFactoryError("record cannot be archived from current state")
            record.state = StrategyFactoryState.ARCHIVED

        record.updated_at = datetime.now(timezone.utc)
        self._refresh(record)
        self._emit(record, action, request.actor, before, record.state, request)
        return record

    @staticmethod
    def _require(record: StrategyFactoryRecord, expected: StrategyFactoryState) -> None:
        if record.state != expected:
            raise StrategyFactoryError(f"action requires {expected.value} state")

    @staticmethod
    def _selected(record: StrategyFactoryRecord):
        return next(item for item in record.candidates if item.candidate_id == record.selected_candidate_id)

    def _refresh(self, record: StrategyFactoryRecord) -> None:
        selected = self._selected(record)
        record.selected_confidence = selected.confidence
        record.selected_robustness = selected.robustness_score
        record.selected_drawdown = selected.maximum_drawdown
        passed = sum(1 for gate in record.validation_gates if gate.passed and gate.score >= gate.minimum_score)
        record.validation_pass_rate = passed / len(record.validation_gates)

    def _emit(
        self,
        record: StrategyFactoryRecord,
        action: str,
        actor: str,
        before: StrategyFactoryState | None,
        after: StrategyFactoryState,
        request: StrategyFactoryActionRequest | None = None,
    ) -> None:
        details = {}
        if request is not None:
            details = {
                "note": request.note,
                "evidence_refs": request.evidence_refs,
                "healthy_cycles": record.consecutive_healthy_cycles,
            }
        self._audit.append(
            AuditEvent(
                record_id=record.record_id,
                workspace_id=record.workspace_id,
                action=action,
                actor=actor,
                from_state=before,
                to_state=after,
                details=details,
            )
        )


service = StrategyFactoryService()
