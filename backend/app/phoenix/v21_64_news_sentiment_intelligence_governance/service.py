from __future__ import annotations

from statistics import pstdev

from .models import (
    AuditEvent,
    NewsSentimentAction,
    NewsSentimentCreate,
    NewsSentimentRecord,
    NewsSentimentState,
    utcnow,
)


class GovernanceError(ValueError):
    pass


class NewsSentimentGovernanceService:
    def __init__(self) -> None:
        self.records: dict[str, NewsSentimentRecord] = {}
        self.audit: list[AuditEvent] = []
        self.source_keys: set[tuple[str, str]] = set()
        self.approval_tokens: set[str] = set()
        self.operation_receipts: set[str] = set()

    def create(self, payload: NewsSentimentCreate) -> NewsSentimentRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self.source_keys:
            raise GovernanceError("duplicate source_key in workspace")
        record = NewsSentimentRecord(
            **payload.model_dump(),
            state=NewsSentimentState.BLOCKED if payload.risk_brain_blocked else NewsSentimentState.DRAFT,
        )
        self._evaluate(record)
        self.records[record.record_id] = record
        self.source_keys.add(key)
        self._audit(record, "create", "system", record.state, record.state)
        return record

    def list(self, workspace_id: str) -> list[NewsSentimentRecord]:
        return [item for item in self.records.values() if item.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> NewsSentimentRecord:
        record = self.records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError(record_id)
        return record

    def act(self, record_id: str, workspace_id: str, command: NewsSentimentAction) -> NewsSentimentRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        if record.risk_brain_blocked and command.action not in {"revoke", "archive"}:
            raise GovernanceError("Risk Brain hard block is authoritative")

        transitions = {
            "prepare-evidence": ({NewsSentimentState.DRAFT}, NewsSentimentState.EVIDENCE_READY),
            "score": ({NewsSentimentState.EVIDENCE_READY}, NewsSentimentState.SCORED),
            "prepare-policy": ({NewsSentimentState.SCORED}, NewsSentimentState.POLICY_READY),
            "request-review": ({NewsSentimentState.POLICY_READY}, NewsSentimentState.REVIEW_REQUIRED),
            "approve": ({NewsSentimentState.REVIEW_REQUIRED}, NewsSentimentState.APPROVED),
            "activate": ({NewsSentimentState.APPROVED}, NewsSentimentState.ACTIVE),
            "confirm-stable": ({NewsSentimentState.MONITORING}, NewsSentimentState.STABLE),
            "escalate": ({NewsSentimentState.ACTIVE, NewsSentimentState.MONITORING, NewsSentimentState.NARRATIVE_SHIFT}, NewsSentimentState.ESCALATED),
            "suspend": ({NewsSentimentState.ACTIVE, NewsSentimentState.MONITORING, NewsSentimentState.NARRATIVE_SHIFT, NewsSentimentState.ESCALATED}, NewsSentimentState.SUSPENDED),
            "resume": ({NewsSentimentState.SUSPENDED}, NewsSentimentState.MONITORING),
            "revoke": (set(NewsSentimentState) - {NewsSentimentState.ARCHIVED}, NewsSentimentState.REVOKED),
            "archive": ({NewsSentimentState.STABLE, NewsSentimentState.REVOKED}, NewsSentimentState.ARCHIVED),
        }

        if command.action == "approve":
            self._consume(command.approval_token, self.approval_tokens, "approval_token")
        if command.action in {"activate", "confirm-stable"}:
            self._consume(command.operation_receipt, self.operation_receipts, "operation_receipt")

        if command.action == "observe":
            if record.state not in {NewsSentimentState.ACTIVE, NewsSentimentState.MONITORING, NewsSentimentState.NARRATIVE_SHIFT}:
                raise GovernanceError("observe not allowed in current state")
            if not command.signals:
                raise GovernanceError("signals required")
            previous = record.sentiment_score
            record.signals = command.signals
            self._evaluate(record)
            shift = abs(record.sentiment_score - previous)
            if record.impact_score >= record.policy.escalation_impact_threshold or "manipulation_risk_exceeded" in record.violations:
                record.state = NewsSentimentState.ESCALATED
                record.stable_cycles = 0
            elif shift >= record.policy.narrative_shift_threshold:
                record.state = NewsSentimentState.NARRATIVE_SHIFT
                record.stable_cycles = 0
            else:
                record.state = NewsSentimentState.MONITORING
                record.stable_cycles += 1
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

    @staticmethod
    def _evaluate(record: NewsSentimentRecord) -> None:
        weights = [max(0.01, s.relevance * s.credibility * s.freshness / 1_000_000) for s in record.signals]
        total = sum(weights)
        record.sentiment_score = round(sum(s.sentiment * w for s, w in zip(record.signals, weights)) / total, 2)
        record.impact_score = round(sum(s.market_impact * w for s, w in zip(record.signals, weights)) / total, 2)
        record.quality_score = round(sum(((s.credibility + s.freshness + s.relevance) / 3) * w for s, w in zip(record.signals, weights)) / total, 2)
        record.confidence_score = round(sum(((s.credibility + s.novelty + (100 - s.manipulation_risk)) / 3) * w for s, w in zip(record.signals, weights)) / total, 2)
        record.manipulation_risk = round(sum(s.manipulation_risk * w for s, w in zip(record.signals, weights)) / total, 2)
        record.narrative_dispersion = round(pstdev([s.sentiment for s in record.signals]), 2) if len(record.signals) > 1 else 0
        violations: list[str] = []
        if record.quality_score < record.policy.minimum_quality_score:
            violations.append("quality_below_minimum")
        if record.confidence_score < record.policy.minimum_confidence_score:
            violations.append("confidence_below_minimum")
        if record.manipulation_risk > record.policy.maximum_manipulation_risk:
            violations.append("manipulation_risk_exceeded")
        record.violations = violations

    @staticmethod
    def _consume(value: str | None, used: set[str], name: str) -> None:
        if not value:
            raise GovernanceError(f"{name} required")
        if value in used:
            raise GovernanceError(f"{name} replay detected")
        used.add(value)

    def _audit(self, record: NewsSentimentRecord, action: str, actor: str, before: NewsSentimentState, after: NewsSentimentState, note: str | None = None) -> None:
        self.audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, note=note))


service = NewsSentimentGovernanceService()
