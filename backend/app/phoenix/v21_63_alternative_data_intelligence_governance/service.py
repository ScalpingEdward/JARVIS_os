from __future__ import annotations

from statistics import pstdev

from .models import (
    AlternativeDataAction,
    AlternativeDataCreate,
    AlternativeDataRecord,
    AlternativeDataState,
    AuditEvent,
    utcnow,
)


class GovernanceError(ValueError):
    pass


class AlternativeDataGovernanceService:
    def __init__(self) -> None:
        self.records: dict[str, AlternativeDataRecord] = {}
        self.audit: list[AuditEvent] = []
        self.source_keys: set[tuple[str, str]] = set()
        self.approval_tokens: set[str] = set()
        self.operation_receipts: set[str] = set()

    def create(self, payload: AlternativeDataCreate) -> AlternativeDataRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self.source_keys:
            raise GovernanceError("duplicate source_key in workspace")
        record = AlternativeDataRecord(
            **payload.model_dump(),
            state=AlternativeDataState.BLOCKED if payload.risk_brain_blocked else AlternativeDataState.DRAFT,
        )
        self._evaluate(record)
        self.records[record.record_id] = record
        self.source_keys.add(key)
        self._audit(record, "create", "system", record.state, record.state)
        return record

    def list(self, workspace_id: str) -> list[AlternativeDataRecord]:
        return [record for record in self.records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> AlternativeDataRecord:
        record = self.records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError(record_id)
        return record

    def act(self, record_id: str, workspace_id: str, command: AlternativeDataAction) -> AlternativeDataRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        if record.risk_brain_blocked and command.action not in {"revoke", "archive"}:
            raise GovernanceError("Risk Brain hard block is authoritative")

        transitions = {
            "prepare-evidence": ({AlternativeDataState.DRAFT}, AlternativeDataState.EVIDENCE_READY),
            "score": ({AlternativeDataState.EVIDENCE_READY}, AlternativeDataState.SCORED),
            "prepare-policy": ({AlternativeDataState.SCORED}, AlternativeDataState.POLICY_READY),
            "request-review": ({AlternativeDataState.POLICY_READY}, AlternativeDataState.REVIEW_REQUIRED),
            "approve": ({AlternativeDataState.REVIEW_REQUIRED}, AlternativeDataState.APPROVED),
            "activate": ({AlternativeDataState.APPROVED}, AlternativeDataState.ACTIVE),
            "confirm-stable": ({AlternativeDataState.MONITORING, AlternativeDataState.SIGNAL_SHIFT}, AlternativeDataState.STABLE),
            "escalate": ({AlternativeDataState.ACTIVE, AlternativeDataState.MONITORING, AlternativeDataState.SIGNAL_SHIFT}, AlternativeDataState.ESCALATED),
            "suspend": ({AlternativeDataState.ACTIVE, AlternativeDataState.MONITORING, AlternativeDataState.SIGNAL_SHIFT, AlternativeDataState.ESCALATED}, AlternativeDataState.SUSPENDED),
            "resume": ({AlternativeDataState.SUSPENDED}, AlternativeDataState.MONITORING),
            "revoke": (set(AlternativeDataState) - {AlternativeDataState.ARCHIVED}, AlternativeDataState.REVOKED),
            "archive": ({AlternativeDataState.STABLE, AlternativeDataState.REVOKED}, AlternativeDataState.ARCHIVED),
        }

        if command.action == "approve":
            self._consume(command.approval_token, self.approval_tokens, "approval_token")
        if command.action in {"activate", "confirm-stable"}:
            self._consume(command.operation_receipt, self.operation_receipts, "operation_receipt")

        if command.action == "observe":
            if record.state not in {AlternativeDataState.ACTIVE, AlternativeDataState.MONITORING, AlternativeDataState.SIGNAL_SHIFT, AlternativeDataState.STABLE}:
                raise GovernanceError("observe not allowed in current state")
            if not command.signals:
                raise GovernanceError("signals required")
            previous = record.composite_score
            record.signals = command.signals
            self._evaluate(record)
            delta = abs(record.composite_score - previous)
            if record.violations or delta >= record.policy.escalation_threshold:
                record.state = AlternativeDataState.ESCALATED
                record.stable_cycles = 0
            elif delta >= record.policy.signal_shift_threshold:
                record.state = AlternativeDataState.SIGNAL_SHIFT
                record.stable_cycles = 0
            else:
                record.stable_cycles += 1
                record.state = (
                    AlternativeDataState.STABLE
                    if record.stable_cycles >= record.policy.stable_cycles_required
                    else AlternativeDataState.MONITORING
                )
        else:
            allowed, target = transitions[command.action]
            if record.state not in allowed:
                raise GovernanceError(f"{command.action} not allowed from {record.state.value}")
            if command.action == "confirm-stable" and record.stable_cycles < record.policy.stable_cycles_required:
                raise GovernanceError("stable observation cycles incomplete")
            record.state = target

        record.updated_at = utcnow()
        self._audit(record, command.action, command.actor, before, record.state, command.note)
        return record

    def _evaluate(self, record: AlternativeDataRecord) -> None:
        signals = record.signals
        weights = [max(1.0, item.confidence * item.coverage_score / 100) for item in signals]
        total_weight = sum(weights)
        record.composite_score = round(
            sum(item.normalized_score * weight for item, weight in zip(signals, weights)) / total_weight,
            2,
        )
        record.confidence_score = round(sum(item.confidence for item in signals) / len(signals), 2)
        freshness_scores = [max(0.0, 100 - item.freshness_minutes / record.policy.maximum_freshness_minutes * 100) for item in signals]
        record.data_quality_score = round(
            sum((item.confidence + item.coverage_score + freshness) / 3 for item, freshness in zip(signals, freshness_scores)) / len(signals),
            2,
        )
        record.signal_dispersion = round(pstdev([item.normalized_score for item in signals]) if len(signals) > 1 else 0.0, 2)
        violations: list[str] = []
        if record.confidence_score < record.policy.minimum_confidence:
            violations.append("confidence_below_minimum")
        if sum(item.coverage_score for item in signals) / len(signals) < record.policy.minimum_coverage:
            violations.append("coverage_below_minimum")
        if any(item.freshness_minutes > record.policy.maximum_freshness_minutes for item in signals):
            violations.append("stale_data_detected")
        if len({item.provenance_ref for item in signals}) != len(signals):
            violations.append("provenance_collision")
        record.violations = violations

    @staticmethod
    def _consume(value: str | None, used: set[str], name: str) -> None:
        if not value:
            raise GovernanceError(f"{name} required")
        if value in used:
            raise GovernanceError(f"{name} replay detected")
        used.add(value)

    def _audit(self, record: AlternativeDataRecord, action: str, actor: str, before: AlternativeDataState, after: AlternativeDataState, note: str | None = None) -> None:
        self.audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, note=note))


service = AlternativeDataGovernanceService()
