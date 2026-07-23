from __future__ import annotations

from statistics import pstdev

from .models import AuditEvent, FlowAction, FlowCreate, FlowRecord, FlowState, utcnow


class GovernanceError(ValueError):
    pass


class InstitutionalFlowGovernanceService:
    def __init__(self) -> None:
        self.records: dict[str, FlowRecord] = {}
        self.audit: list[AuditEvent] = []
        self.source_keys: set[tuple[str, str]] = set()
        self.approval_tokens: set[str] = set()
        self.operation_receipts: set[str] = set()

    def create(self, payload: FlowCreate) -> FlowRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self.source_keys:
            raise GovernanceError("duplicate source_key in workspace")
        record = FlowRecord(
            **payload.model_dump(),
            state=FlowState.BLOCKED if payload.risk_brain_blocked else FlowState.DRAFT,
        )
        self._evaluate(record)
        self.records[record.record_id] = record
        self.source_keys.add(key)
        self._audit(record, "create", "system", record.state, record.state)
        return record

    def list(self, workspace_id: str) -> list[FlowRecord]:
        return [record for record in self.records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> FlowRecord:
        record = self.records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError(record_id)
        return record

    def act(self, record_id: str, workspace_id: str, command: FlowAction) -> FlowRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        if record.risk_brain_blocked and command.action not in {"revoke", "archive"}:
            raise GovernanceError("Risk Brain hard block is authoritative")

        transitions = {
            "prepare-evidence": ({FlowState.DRAFT}, FlowState.EVIDENCE_READY),
            "score": ({FlowState.EVIDENCE_READY}, FlowState.SCORED),
            "prepare-policy": ({FlowState.SCORED, FlowState.FLOW_SHIFT}, FlowState.POLICY_READY),
            "request-review": ({FlowState.POLICY_READY}, FlowState.REVIEW_REQUIRED),
            "approve": ({FlowState.REVIEW_REQUIRED}, FlowState.APPROVED),
            "activate": ({FlowState.APPROVED}, FlowState.ACTIVE),
            "suspend": ({FlowState.ACTIVE, FlowState.MONITORING, FlowState.STABLE, FlowState.FLOW_SHIFT, FlowState.ESCALATED}, FlowState.SUSPENDED),
            "resume": ({FlowState.SUSPENDED}, FlowState.MONITORING),
            "escalate": ({FlowState.SCORED, FlowState.ACTIVE, FlowState.MONITORING, FlowState.FLOW_SHIFT}, FlowState.ESCALATED),
            "revoke": (set(FlowState) - {FlowState.ARCHIVED}, FlowState.REVOKED),
            "archive": ({FlowState.REVOKED, FlowState.STABLE}, FlowState.ARCHIVED),
        }

        if command.action == "approve":
            self._consume(command.approval_token, self.approval_tokens, "approval_token")
        if command.action == "activate":
            self._consume(command.operation_receipt, self.operation_receipts, "operation_receipt")

        if command.action == "observe":
            if record.state not in {FlowState.ACTIVE, FlowState.MONITORING, FlowState.STABLE, FlowState.FLOW_SHIFT}:
                raise GovernanceError("observe not allowed in current state")
            if not command.signals:
                raise GovernanceError("signals required")
            previous = record.net_flow_score
            record.signals = command.signals
            self._evaluate(record)
            shift = abs(record.net_flow_score - previous)
            if record.institutional_pressure_score >= record.policy.escalation_threshold or record.violations:
                record.state = FlowState.ESCALATED
                record.stable_cycles = 0
            elif shift >= record.policy.shift_threshold:
                record.state = FlowState.FLOW_SHIFT
                record.stable_cycles = 0
            else:
                record.stable_cycles += 1
                record.state = FlowState.STABLE if record.stable_cycles >= record.policy.stable_cycles_required else FlowState.MONITORING
        else:
            allowed, target = transitions[command.action]
            if record.state not in allowed:
                raise GovernanceError(f"{command.action} not allowed from {record.state.value}")
            record.state = target

        record.updated_at = utcnow()
        self._audit(record, command.action, command.actor, before, record.state, command.note)
        return record

    def _evaluate(self, record: FlowRecord) -> None:
        weights = [max(item.notional_usd, 1.0) for item in record.signals]
        total = sum(weights)
        signed_values: list[float] = []
        pressures: list[float] = []
        for item, weight in zip(record.signals, weights):
            sign = 1 if item.direction in {"inflow", "accumulation"} else -1 if item.direction in {"outflow", "distribution"} else 0
            magnitude = min(100.0, item.participation_pct * 0.45 + item.persistence_score * 0.35 + item.confidence * 0.2)
            signed_values.append(sign * magnitude)
            pressures.append(magnitude)
        record.net_flow_score = round(sum(value * weight for value, weight in zip(signed_values, weights)) / total, 2)
        record.institutional_pressure_score = round(sum(value * weight for value, weight in zip(pressures, weights)) / total, 2)
        record.concentration_risk = round(sum(item.concentration_score * weight for item, weight in zip(record.signals, weights)) / total, 2)
        record.data_quality_score = round(sum(((item.freshness + item.provenance_score) / 2) * weight for item, weight in zip(record.signals, weights)) / total, 2)
        record.confidence_score = round(sum(item.confidence * weight for item, weight in zip(record.signals, weights)) / total, 2)
        record.flow_dispersion = round(pstdev(signed_values) if len(signed_values) > 1 else 0.0, 2)
        violations: list[str] = []
        if record.confidence_score < record.policy.minimum_confidence:
            violations.append("confidence_below_minimum")
        if record.data_quality_score < record.policy.minimum_data_quality:
            violations.append("data_quality_below_minimum")
        if record.concentration_risk > record.policy.maximum_concentration:
            violations.append("concentration_exceeded")
        record.violations = violations

    @staticmethod
    def _consume(value: str | None, used: set[str], name: str) -> None:
        if not value:
            raise GovernanceError(f"{name} required")
        if value in used:
            raise GovernanceError(f"{name} replay detected")
        used.add(value)

    def _audit(self, record: FlowRecord, action: str, actor: str, before: FlowState, after: FlowState, note: str | None = None) -> None:
        self.audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, note=note))


service = InstitutionalFlowGovernanceService()
