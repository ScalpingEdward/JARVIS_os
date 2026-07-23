from __future__ import annotations

from collections import defaultdict

from .models import AuditEvent, RotationAction, RotationCreate, RotationRecord, RotationState, utcnow


class GovernanceError(ValueError):
    pass


class PortfolioRotationGovernanceService:
    def __init__(self) -> None:
        self.records: dict[str, RotationRecord] = {}
        self.audit: list[AuditEvent] = []
        self.source_keys: set[tuple[str, str]] = set()
        self.approval_tokens: set[str] = set()
        self.operation_receipts: set[str] = set()

    def create(self, payload: RotationCreate) -> RotationRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self.source_keys:
            raise GovernanceError("duplicate source_key in workspace")
        record = RotationRecord(
            **payload.model_dump(),
            state=RotationState.BLOCKED if payload.risk_brain_blocked else RotationState.DRAFT,
        )
        self._evaluate(record)
        self.records[record.record_id] = record
        self.source_keys.add(key)
        self._audit(record, "create", "system", record.state, record.state)
        return record

    def list(self, workspace_id: str) -> list[RotationRecord]:
        return [record for record in self.records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> RotationRecord:
        record = self.records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError(record_id)
        return record

    def act(self, record_id: str, workspace_id: str, command: RotationAction) -> RotationRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        if record.risk_brain_blocked and command.action not in {"revoke", "archive"}:
            raise GovernanceError("Risk Brain hard block is authoritative")

        transitions = {
            "prepare-evidence": ({RotationState.DRAFT}, RotationState.EVIDENCE_READY),
            "analyze": ({RotationState.EVIDENCE_READY}, RotationState.ANALYZED),
            "prepare-rotation": ({RotationState.ANALYZED}, RotationState.ROTATION_READY),
            "request-review": ({RotationState.ROTATION_READY}, RotationState.REVIEW_REQUIRED),
            "approve": ({RotationState.REVIEW_REQUIRED}, RotationState.APPROVED),
            "start-rotation": ({RotationState.APPROVED}, RotationState.ROTATING),
            "require-rebalance": ({RotationState.MONITORING, RotationState.VERIFIED}, RotationState.REBALANCE_REQUIRED),
            "escalate": ({RotationState.ROTATING, RotationState.MONITORING, RotationState.REBALANCE_REQUIRED}, RotationState.ESCALATED),
            "suspend": ({RotationState.ROTATING, RotationState.MONITORING, RotationState.REBALANCE_REQUIRED, RotationState.ESCALATED}, RotationState.SUSPENDED),
            "resume": ({RotationState.SUSPENDED}, RotationState.MONITORING),
            "revoke": (set(RotationState) - {RotationState.ARCHIVED}, RotationState.REVOKED),
            "archive": ({RotationState.VERIFIED, RotationState.REVOKED}, RotationState.ARCHIVED),
        }

        if command.action == "approve":
            if not command.approval_token:
                raise GovernanceError("approval_token required")
            if command.approval_token in self.approval_tokens:
                raise GovernanceError("approval_token replay detected")
            self.approval_tokens.add(command.approval_token)

        if command.action in {"start-rotation", "require-rebalance"}:
            if not command.operation_receipt:
                raise GovernanceError("operation_receipt required")
            if command.operation_receipt in self.operation_receipts:
                raise GovernanceError("operation_receipt replay detected")
            self.operation_receipts.add(command.operation_receipt)

        if command.action == "observe":
            if record.state not in {RotationState.ROTATING, RotationState.MONITORING, RotationState.REBALANCE_REQUIRED}:
                raise GovernanceError("observe not allowed in current state")
            if command.sleeves:
                record.sleeves = command.sleeves
            self._evaluate(record)
            if record.violations:
                record.verification_cycles = 0
                record.state = RotationState.ESCALATED
            else:
                record.verification_cycles += 1
                record.state = (
                    RotationState.VERIFIED
                    if record.verification_cycles >= record.policy.verification_cycles_required
                    else RotationState.MONITORING
                )
        else:
            allowed, target = transitions[command.action]
            if record.state not in allowed:
                raise GovernanceError(f"{command.action} not allowed from {record.state.value}")
            record.state = target

        record.updated_at = utcnow()
        self._audit(record, command.action, command.actor, before, record.state, command.note)
        return record

    def _evaluate(self, record: RotationRecord) -> None:
        total_weight = sum(s.proposed_weight_pct for s in record.sleeves) or 1
        record.projected_drawdown_pct = round(
            sum(s.proposed_weight_pct * s.drawdown_pct for s in record.sleeves) / total_weight, 2
        )
        record.turnover_pct = round(
            sum(abs(s.proposed_weight_pct - s.current_weight_pct) for s in record.sleeves) / 2, 2
        )
        record.weighted_regime_fit = round(
            sum(s.proposed_weight_pct * s.regime_fit_score for s in record.sleeves) / total_weight, 2
        )
        record.weighted_liquidity = round(
            sum(s.proposed_weight_pct * s.liquidity_score for s in record.sleeves) / total_weight, 2
        )
        record.weighted_confidence = round(
            sum(s.proposed_weight_pct * s.confidence for s in record.sleeves) / total_weight, 4
        )

        violations: list[str] = []
        bucket_weights: defaultdict[str, float] = defaultdict(float)
        for sleeve in record.sleeves:
            bucket_weights[sleeve.correlation_bucket] += sleeve.proposed_weight_pct
            if sleeve.proposed_weight_pct > record.policy.maximum_single_sleeve_weight_pct:
                violations.append(f"single_sleeve_weight_exceeded:{sleeve.sleeve_id}")
            if sleeve.proposed_capital > sleeve.capacity_limit:
                violations.append(f"capacity_exceeded:{sleeve.sleeve_id}")
            if sleeve.regime_fit_score < record.policy.minimum_regime_fit:
                violations.append(f"regime_fit_below_minimum:{sleeve.sleeve_id}")
            if sleeve.liquidity_score < record.policy.minimum_liquidity_score:
                violations.append(f"liquidity_below_minimum:{sleeve.sleeve_id}")
            if sleeve.confidence < record.policy.minimum_confidence:
                violations.append(f"confidence_below_minimum:{sleeve.sleeve_id}")
        for bucket, weight in bucket_weights.items():
            if weight > record.policy.maximum_bucket_weight_pct:
                violations.append(f"correlation_bucket_weight_exceeded:{bucket}")
        if record.projected_drawdown_pct > record.policy.maximum_projected_drawdown_pct:
            violations.append("projected_drawdown_exceeded")
        if record.turnover_pct > record.policy.maximum_turnover_pct:
            violations.append("turnover_exceeded")
        record.violations = violations

    def _audit(
        self,
        record: RotationRecord,
        action: str,
        actor: str,
        from_state: RotationState,
        to_state: RotationState,
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


service = PortfolioRotationGovernanceService()
