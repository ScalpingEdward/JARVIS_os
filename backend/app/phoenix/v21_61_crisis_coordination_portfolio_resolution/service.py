from __future__ import annotations

from .models import AuditEvent, CrisisAction, CrisisCreate, CrisisRecord, CrisisState, utcnow


class GovernanceError(ValueError):
    pass


class CrisisGovernanceService:
    def __init__(self) -> None:
        self.records: dict[str, CrisisRecord] = {}
        self.audit: list[AuditEvent] = []
        self.source_keys: set[tuple[str, str]] = set()
        self.approval_tokens: set[str] = set()
        self.operation_receipts: set[str] = set()

    def create(self, payload: CrisisCreate) -> CrisisRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self.source_keys:
            raise GovernanceError("duplicate source_key in workspace")
        record = CrisisRecord(
            **payload.model_dump(),
            state=CrisisState.BLOCKED if payload.risk_brain_blocked else CrisisState.DRAFT,
        )
        self._evaluate(record)
        self.records[record.record_id] = record
        self.source_keys.add(key)
        self._audit(record, "create", "system", record.state, record.state)
        return record

    def list(self, workspace_id: str) -> list[CrisisRecord]:
        return [record for record in self.records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> CrisisRecord:
        record = self.records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError(record_id)
        return record

    def act(self, record_id: str, workspace_id: str, command: CrisisAction) -> CrisisRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        if record.risk_brain_blocked and command.action not in {"revoke", "archive"}:
            raise GovernanceError("Risk Brain hard block is authoritative")

        transitions = {
            "prepare-evidence": ({CrisisState.DRAFT}, CrisisState.EVIDENCE_READY),
            "assess": ({CrisisState.EVIDENCE_READY}, CrisisState.ASSESSED),
            "prepare-coordination": ({CrisisState.ASSESSED}, CrisisState.COORDINATION_READY),
            "request-review": ({CrisisState.COORDINATION_READY}, CrisisState.REVIEW_REQUIRED),
            "approve": ({CrisisState.REVIEW_REQUIRED}, CrisisState.APPROVED),
            "activate-coordination": ({CrisisState.APPROVED}, CrisisState.COORDINATING),
            "confirm-containment": ({CrisisState.COORDINATING}, CrisisState.CONTAINING),
            "prepare-resolution": ({CrisisState.CONTAINING, CrisisState.STABILIZED}, CrisisState.RESOLUTION_READY),
            "execute-resolution": ({CrisisState.RESOLUTION_READY}, CrisisState.RESOLVING),
            "begin-recovery-monitoring": ({CrisisState.STABILIZED, CrisisState.RESOLVING}, CrisisState.RECOVERY_MONITORING),
            "confirm-resolved": ({CrisisState.RECOVERY_MONITORING}, CrisisState.RESOLVED),
            "escalate": ({CrisisState.ASSESSED, CrisisState.COORDINATING, CrisisState.CONTAINING, CrisisState.RESOLVING, CrisisState.RECOVERY_MONITORING}, CrisisState.ESCALATED),
            "suspend": ({CrisisState.COORDINATING, CrisisState.CONTAINING, CrisisState.RESOLVING, CrisisState.RECOVERY_MONITORING, CrisisState.ESCALATED}, CrisisState.SUSPENDED),
            "resume": ({CrisisState.SUSPENDED}, CrisisState.COORDINATING),
            "revoke": (set(CrisisState) - {CrisisState.ARCHIVED}, CrisisState.REVOKED),
            "archive": ({CrisisState.RESOLVED, CrisisState.REVOKED}, CrisisState.ARCHIVED),
        }

        if command.action == "approve":
            self._consume(command.approval_token, self.approval_tokens, "approval_token")
        if command.action in {"activate-coordination", "execute-resolution", "confirm-resolved"}:
            self._consume(command.operation_receipt, self.operation_receipts, "operation_receipt")

        if command.action == "observe":
            if record.state not in {CrisisState.COORDINATING, CrisisState.CONTAINING, CrisisState.RESOLVING, CrisisState.RECOVERY_MONITORING, CrisisState.STABILIZED}:
                raise GovernanceError("observe not allowed in current state")
            if not command.portfolios:
                raise GovernanceError("portfolios required")
            record.portfolios = command.portfolios
            self._evaluate(record)
            if record.crisis_score >= record.policy.emergency_score_threshold or "projected_loss_exceeded" in record.violations:
                record.state = CrisisState.ESCALATED
                record.stabilization_cycles = 0
                record.resolution_cycles = 0
            elif record.violations:
                record.state = CrisisState.CONTAINING
                record.stabilization_cycles = 0
                record.resolution_cycles = 0
            elif record.state == CrisisState.RECOVERY_MONITORING:
                record.resolution_cycles += 1
                if record.resolution_cycles >= record.policy.resolution_cycles_required:
                    record.state = CrisisState.RECOVERY_MONITORING
            else:
                record.stabilization_cycles += 1
                record.state = CrisisState.STABILIZED if record.stabilization_cycles >= record.policy.stabilization_cycles_required else CrisisState.CONTAINING
        else:
            allowed, target = transitions[command.action]
            if record.state not in allowed:
                raise GovernanceError(f"{command.action} not allowed from {record.state.value}")
            if command.action == "confirm-resolved" and record.resolution_cycles < record.policy.resolution_cycles_required:
                raise GovernanceError("resolution monitoring cycles incomplete")
            record.state = target

        record.updated_at = utcnow()
        self._audit(record, command.action, command.actor, before, record.state, command.note)
        return record

    def _evaluate(self, record: CrisisRecord) -> None:
        total_capital = sum(item.capital for item in record.portfolios)
        record.affected_capital = round(total_capital, 2)
        if not total_capital:
            record.projected_loss_pct = 0
            record.crisis_score = 0
            record.violations = []
            return
        weighted = lambda name: sum(getattr(item, name) * item.capital for item in record.portfolios) / total_capital
        record.projected_loss_pct = round(weighted("projected_loss_pct"), 2)
        drawdown = weighted("drawdown_pct")
        liquidity = weighted("liquidity_score")
        leverage = weighted("leverage")
        stress = weighted("stress_score")
        operations = weighted("operational_health")
        recovery = weighted("recovery_capacity")
        leverage_score = min(100.0, leverage * 18)
        record.crisis_score = round(
            stress * 0.25 + min(100.0, drawdown / record.policy.maximum_drawdown_pct * 100) * 0.2
            + (100 - liquidity) * 0.15 + min(100.0, record.projected_loss_pct / record.policy.maximum_projected_loss_pct * 100) * 0.2
            + leverage_score * 0.08 + (100 - operations) * 0.07 + (100 - recovery) * 0.05,
            2,
        )
        violations: list[str] = []
        if record.projected_loss_pct > record.policy.maximum_projected_loss_pct: violations.append("projected_loss_exceeded")
        if drawdown > record.policy.maximum_drawdown_pct: violations.append("drawdown_exceeded")
        if liquidity < record.policy.minimum_liquidity_score: violations.append("liquidity_below_minimum")
        if operations < record.policy.minimum_operational_health: violations.append("operational_health_below_minimum")
        if record.crisis_score >= record.policy.crisis_score_threshold: violations.append("crisis_score_exceeded")
        record.violations = violations

    @staticmethod
    def _consume(value: str | None, used: set[str], name: str) -> None:
        if not value:
            raise GovernanceError(f"{name} required")
        if value in used:
            raise GovernanceError(f"{name} replay detected")
        used.add(value)

    def _audit(self, record: CrisisRecord, action: str, actor: str, before: CrisisState, after: CrisisState, note: str | None = None) -> None:
        self.audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, note=note))


service = CrisisGovernanceService()
