from __future__ import annotations

from .models import AuditEvent, RegimeAction, RegimeCreate, RegimeRecord, RegimeState, utcnow


class GovernanceError(ValueError):
    pass


class RegimeGovernanceService:
    def __init__(self) -> None:
        self.records: dict[str, RegimeRecord] = {}
        self.audit: list[AuditEvent] = []
        self.source_keys: set[tuple[str, str]] = set()
        self.approval_tokens: set[str] = set()
        self.operation_receipts: set[str] = set()

    def create(self, payload: RegimeCreate) -> RegimeRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self.source_keys:
            raise GovernanceError("duplicate source_key in workspace")
        record = RegimeRecord(
            **payload.model_dump(),
            state=RegimeState.BLOCKED if payload.risk_brain_blocked else RegimeState.DRAFT,
        )
        self._evaluate(record)
        self.records[record.record_id] = record
        self.source_keys.add(key)
        self._audit(record, "create", "system", record.state, record.state)
        return record

    def list(self, workspace_id: str) -> list[RegimeRecord]:
        return [r for r in self.records.values() if r.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> RegimeRecord:
        record = self.records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError(record_id)
        return record

    def act(self, record_id: str, workspace_id: str, command: RegimeAction) -> RegimeRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        if record.risk_brain_blocked and command.action not in {"revoke", "archive"}:
            raise GovernanceError("Risk Brain hard block is authoritative")

        transitions = {
            "prepare-evidence": ({RegimeState.DRAFT}, RegimeState.EVIDENCE_READY),
            "classify": ({RegimeState.EVIDENCE_READY}, RegimeState.CLASSIFIED),
            "prepare-adaptation": ({RegimeState.CLASSIFIED, RegimeState.REGIME_SHIFT}, RegimeState.ADAPTATION_READY),
            "request-review": ({RegimeState.ADAPTATION_READY}, RegimeState.REVIEW_REQUIRED),
            "approve": ({RegimeState.REVIEW_REQUIRED}, RegimeState.APPROVED),
            "start-adaptation": ({RegimeState.APPROVED}, RegimeState.ADAPTING),
            "escalate": ({RegimeState.CLASSIFIED, RegimeState.ADAPTING, RegimeState.MONITORING, RegimeState.REGIME_SHIFT}, RegimeState.ESCALATED),
            "suspend": ({RegimeState.ADAPTING, RegimeState.MONITORING, RegimeState.REGIME_SHIFT, RegimeState.ESCALATED}, RegimeState.SUSPENDED),
            "resume": ({RegimeState.SUSPENDED}, RegimeState.MONITORING),
            "revoke": (set(RegimeState) - {RegimeState.ARCHIVED}, RegimeState.REVOKED),
            "archive": ({RegimeState.VALIDATED, RegimeState.REVOKED, RegimeState.ESCALATED}, RegimeState.ARCHIVED),
        }

        if command.action == "approve":
            if not command.approval_token:
                raise GovernanceError("approval_token required")
            if command.approval_token in self.approval_tokens:
                raise GovernanceError("approval_token replay detected")
            self.approval_tokens.add(command.approval_token)

        if command.action in {"start-adaptation", "validate"}:
            if not command.operation_receipt:
                raise GovernanceError("operation_receipt required")
            if command.operation_receipt in self.operation_receipts:
                raise GovernanceError("operation_receipt replay detected")
            self.operation_receipts.add(command.operation_receipt)

        if command.action == "observe":
            if record.state not in {RegimeState.ADAPTING, RegimeState.MONITORING, RegimeState.REGIME_SHIFT}:
                raise GovernanceError("observe not allowed in current state")
            if not command.observation:
                raise GovernanceError("observation required")
            record.observations.append(command.observation)
            self._evaluate(record)
            if record.violations:
                record.validation_cycles = 0
                record.state = RegimeState.ESCALATED if "stress_above_maximum" in record.violations else RegimeState.REGIME_SHIFT
            else:
                record.validation_cycles += 1
                record.state = RegimeState.MONITORING
        elif command.action == "validate":
            if record.state != RegimeState.MONITORING:
                raise GovernanceError("validate not allowed from current state")
            if record.validation_cycles < record.policy.validation_cycles_required:
                raise GovernanceError("insufficient healthy validation cycles")
            if record.violations:
                raise GovernanceError("unresolved regime violations")
            record.state = RegimeState.VALIDATED
        else:
            allowed, target = transitions[command.action]
            if record.state not in allowed:
                raise GovernanceError(f"{command.action} not allowed from {record.state.value}")
            record.state = target

        record.updated_at = utcnow()
        self._audit(record, command.action, command.actor, before, record.state, command.note)
        return record

    def _evaluate(self, record: RegimeRecord) -> None:
        current = record.observations[-1]
        previous = record.observations[-2] if len(record.observations) > 1 else current
        dimensions = ("trend_score", "volatility_score", "liquidity_score", "dispersion_score", "correlation_score", "stress_score")
        record.regime_distance = round(sum(abs(getattr(current, d) - getattr(previous, d)) for d in dimensions) / len(dimensions), 2)
        record.regime_confidence = current.confidence
        if current.stress_score >= 70:
            record.regime_label = "stressed"
        elif current.volatility_score >= 65 and current.trend_score >= 60:
            record.regime_label = "volatile-trend"
        elif current.volatility_score <= 40 and current.trend_score >= 60:
            record.regime_label = "stable-trend"
        elif current.trend_score <= 40:
            record.regime_label = "range-bound"
        else:
            record.regime_label = "transitional"
        violations: list[str] = []
        if current.confidence < record.policy.minimum_confidence:
            violations.append("confidence_below_minimum")
        if current.stress_score > record.policy.maximum_stress_score:
            violations.append("stress_above_maximum")
        if current.liquidity_score < record.policy.minimum_liquidity_score:
            violations.append("liquidity_below_minimum")
        if record.regime_distance > record.policy.regime_shift_distance:
            violations.append("regime_shift_detected")
        record.violations = violations

    def _audit(self, record: RegimeRecord, action: str, actor: str, before: RegimeState, after: RegimeState, note: str | None = None) -> None:
        self.audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, note=note))


service = RegimeGovernanceService()
