from __future__ import annotations

from .models import (
    AuditEvent,
    RecoveryAction,
    RecoveryCreate,
    RecoveryRecord,
    RecoveryState,
    RevalidationGate,
    utcnow,
)


class GovernanceError(ValueError):
    pass


class StrategyRecoveryGovernanceService:
    def __init__(self) -> None:
        self.records: dict[str, RecoveryRecord] = {}
        self.audit: list[AuditEvent] = []
        self.source_keys: set[tuple[str, str]] = set()
        self.approval_tokens: set[str] = set()
        self.operation_receipts: set[str] = set()

    def create(self, payload: RecoveryCreate) -> RecoveryRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self.source_keys:
            raise GovernanceError("duplicate source_key in workspace")
        record = RecoveryRecord(
            **payload.model_dump(),
            state=RecoveryState.BLOCKED if payload.risk_brain_blocked else RecoveryState.DRAFT,
        )
        self._evaluate(record)
        self.records[record.record_id] = record
        self.source_keys.add(key)
        self._audit(record, "create", "system", record.state, record.state)
        return record

    def list(self, workspace_id: str) -> list[RecoveryRecord]:
        return [record for record in self.records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> RecoveryRecord:
        record = self.records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError(record_id)
        return record

    def act(self, record_id: str, workspace_id: str, command: RecoveryAction) -> RecoveryRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        if record.risk_brain_blocked and command.action not in {"revoke", "archive"}:
            raise GovernanceError("Risk Brain hard block is authoritative")

        transitions = {
            "prepare-evidence": ({RecoveryState.DRAFT}, RecoveryState.EVIDENCE_READY),
            "diagnose": ({RecoveryState.EVIDENCE_READY}, RecoveryState.DIAGNOSED),
            "prepare-plan": ({RecoveryState.DIAGNOSED}, RecoveryState.PLAN_READY),
            "request-review": ({RecoveryState.PLAN_READY}, RecoveryState.REVIEW_REQUIRED),
            "approve": ({RecoveryState.REVIEW_REQUIRED}, RecoveryState.APPROVED),
            "start-recovery": ({RecoveryState.APPROVED}, RecoveryState.RECOVERING),
            "start-revalidation": ({RecoveryState.RECOVERING}, RecoveryState.REVALIDATING),
            "complete-revalidation": ({RecoveryState.REVALIDATING}, RecoveryState.REVALIDATED),
            "authorize-conditional-return": ({RecoveryState.REVALIDATED}, RecoveryState.CONDITIONAL_RETURN),
            "restore": ({RecoveryState.CONDITIONAL_RETURN}, RecoveryState.RESTORED),
            "escalate": (
                {
                    RecoveryState.RECOVERING,
                    RecoveryState.REVALIDATING,
                    RecoveryState.REVALIDATED,
                    RecoveryState.CONDITIONAL_RETURN,
                },
                RecoveryState.ESCALATED,
            ),
            "suspend": (
                {
                    RecoveryState.RECOVERING,
                    RecoveryState.REVALIDATING,
                    RecoveryState.CONDITIONAL_RETURN,
                    RecoveryState.ESCALATED,
                },
                RecoveryState.SUSPENDED,
            ),
            "resume": ({RecoveryState.SUSPENDED}, RecoveryState.RECOVERING),
            "retire": (
                {RecoveryState.ESCALATED, RecoveryState.SUSPENDED, RecoveryState.CONDITIONAL_RETURN},
                RecoveryState.RETIRED,
            ),
            "revoke": (set(RecoveryState) - {RecoveryState.ARCHIVED}, RecoveryState.REVOKED),
            "archive": (
                {RecoveryState.RESTORED, RecoveryState.RETIRED, RecoveryState.REVOKED},
                RecoveryState.ARCHIVED,
            ),
        }

        if command.action == "approve":
            self._consume_approval_token(command.approval_token)

        if command.action in {
            "start-recovery",
            "start-revalidation",
            "authorize-conditional-return",
            "restore",
            "retire",
        }:
            self._consume_operation_receipt(command.operation_receipt)

        if command.action == "observe":
            if record.state not in {
                RecoveryState.RECOVERING,
                RecoveryState.REVALIDATING,
                RecoveryState.CONDITIONAL_RETURN,
            }:
                raise GovernanceError("observe not allowed in current state")
            if command.observation is None:
                raise GovernanceError("observation required")
            record.observations.append(command.observation)
            self._evaluate(record)
            if record.violations:
                record.healthy_cycles = 0
                record.state = RecoveryState.ESCALATED
            else:
                record.healthy_cycles += 1
        else:
            if command.action not in transitions:
                raise GovernanceError("unknown action")
            allowed, target = transitions[command.action]
            if record.state not in allowed:
                raise GovernanceError(f"{command.action} not allowed from {record.state.value}")

            if command.action == "start-revalidation" and record.healthy_cycles < record.policy.required_healthy_cycles:
                raise GovernanceError("insufficient healthy recovery cycles")

            if command.action == "complete-revalidation":
                if command.gate_updates:
                    self._apply_gate_updates(record, command.gate_updates)
                self._evaluate(record)
                if record.revalidation_pass_rate < record.policy.minimum_revalidation_pass_rate:
                    raise GovernanceError("revalidation gates did not meet required pass rate")
                if record.violations:
                    raise GovernanceError("revalidation blocked by active violations")

            if command.action == "authorize-conditional-return":
                record.recommended_return_capital = round(
                    record.baseline_capital * record.policy.conditional_return_capital_pct / 100,
                    2,
                )

            if command.action == "restore":
                if record.healthy_cycles < record.policy.required_healthy_cycles:
                    raise GovernanceError("conditional return has insufficient healthy cycles")
                record.recommended_return_capital = record.baseline_capital

            record.state = target

        record.updated_at = utcnow()
        self._audit(record, command.action, command.actor, before, record.state, command.note)
        return record

    def _consume_approval_token(self, token: str | None) -> None:
        if not token:
            raise GovernanceError("approval_token required")
        if token in self.approval_tokens:
            raise GovernanceError("approval_token replay detected")
        self.approval_tokens.add(token)

    def _consume_operation_receipt(self, receipt: str | None) -> None:
        if not receipt:
            raise GovernanceError("operation_receipt required")
        if receipt in self.operation_receipts:
            raise GovernanceError("operation_receipt replay detected")
        self.operation_receipts.add(receipt)

    def _apply_gate_updates(self, record: RecoveryRecord, updates: list[RevalidationGate]) -> None:
        existing = {gate.gate_id: gate for gate in record.gates}
        for update in updates:
            if update.gate_id not in existing:
                raise GovernanceError(f"unknown revalidation gate: {update.gate_id}")
            existing[update.gate_id] = update
        record.gates = list(existing.values())

    def _evaluate(self, record: RecoveryRecord) -> None:
        observation = record.observations[-1]
        profitability = min(100.0, max(0.0, 50 + observation.alpha_pct * 8))
        drawdown = max(
            0.0,
            100 - observation.drawdown_pct / record.policy.maximum_recovery_drawdown_pct * 100,
        )
        quality = min(
            100.0,
            max(0.0, 40 + observation.sharpe * 20 + (observation.profit_factor - 1) * 30),
        )
        record.recovery_health_score = round(
            profitability * 0.2
            + drawdown * 0.2
            + quality * 0.15
            + observation.execution_quality_score * 0.15
            + observation.regime_fit_score * 0.1
            + observation.liquidity_score * 0.1
            + observation.confidence * 100 * 0.1,
            2,
        )
        record.revalidation_pass_rate = round(
            sum(1 for gate in record.gates if gate.passed) / len(record.gates),
            4,
        )
        violations: list[str] = []
        if observation.drawdown_pct > record.policy.maximum_recovery_drawdown_pct:
            violations.append("maximum_recovery_drawdown_exceeded")
        if observation.regime_fit_score < record.policy.minimum_regime_fit_score:
            violations.append("regime_fit_below_minimum")
        if observation.execution_quality_score < record.policy.minimum_execution_quality_score:
            violations.append("execution_quality_below_minimum")
        if observation.liquidity_score < record.policy.minimum_liquidity_score:
            violations.append("liquidity_below_minimum")
        if observation.confidence < record.policy.minimum_confidence:
            violations.append("confidence_below_minimum")
        record.violations = violations

    def _audit(
        self,
        record: RecoveryRecord,
        action: str,
        actor: str,
        from_state: RecoveryState,
        to_state: RecoveryState,
        note: str | None = None,
    ) -> None:
        self.audit.append(
            AuditEvent(
                record_id=record.record_id,
                workspace_id=record.workspace_id,
                action=action,
                actor=actor,
                from_state=from_state,
                to_state=to_state,
                note=note,
            )
        )


service = StrategyRecoveryGovernanceService()
