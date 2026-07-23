from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AuditEvent,
    CapitalDeploymentRecord,
    DeploymentActionRequest,
    DeploymentCreate,
    DeploymentState,
    RiskDecision,
)


class CapitalDeploymentError(RuntimeError):
    pass


class CapitalDeploymentService:
    def __init__(self) -> None:
        self._records: dict[str, CapitalDeploymentRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: DeploymentCreate) -> CapitalDeploymentRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise CapitalDeploymentError("duplicate source key")
        record = CapitalDeploymentRecord(**payload.model_dump())
        self._refresh(record)
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> CapitalDeploymentRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise CapitalDeploymentError("capital deployment record not found")
        return record

    def list(self, workspace_id: str) -> list[CapitalDeploymentRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: DeploymentActionRequest) -> CapitalDeploymentRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, DeploymentState.DRAFT)
            record.state = DeploymentState.BLOCKED if record.risk_decision == RiskDecision.BLOCK else DeploymentState.EVIDENCE_READY
        elif action == "analyze":
            self._require(record, DeploymentState.EVIDENCE_READY)
            self._refresh(record)
            record.state = DeploymentState.ESCALATED if self._breached(record) else DeploymentState.ANALYZED
        elif action == "prepare-deployment":
            self._require(record, DeploymentState.ANALYZED)
            if self._breached(record):
                raise CapitalDeploymentError("deployment constraints breached")
            record.state = DeploymentState.DEPLOYMENT_READY
        elif action == "request-review":
            self._require(record, DeploymentState.DEPLOYMENT_READY)
            record.state = DeploymentState.REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, DeploymentState.REVIEW_REQUIRED)
            if not request.approval_token:
                raise CapitalDeploymentError("approval token is required")
            if request.approval_token in self._approval_tokens:
                raise CapitalDeploymentError("approval token replay detected")
            self._approval_tokens.add(request.approval_token)
            record.approval_actor = request.actor
            record.state = DeploymentState.APPROVED
        elif action == "deploy":
            self._require(record, DeploymentState.APPROVED)
            if record.risk_decision == RiskDecision.BLOCK:
                raise CapitalDeploymentError("Risk Brain blocks deployment")
            if not request.receipt_id:
                raise CapitalDeploymentError("deployment receipt is required")
            if request.receipt_id in self._receipt_ids:
                raise CapitalDeploymentError("deployment receipt replay detected")
            self._receipt_ids.add(request.receipt_id)
            record.deployment_evidence.extend(request.evidence_refs)
            record.state = DeploymentState.DEPLOYING
        elif action == "record-cycle":
            self._require(record, DeploymentState.DEPLOYING, DeploymentState.MONITORING)
            if request.cycle_healthy is None:
                raise CapitalDeploymentError("cycle_healthy is required")
            healthy = request.cycle_healthy
            if request.observed_drawdown is not None and request.observed_drawdown > record.maximum_portfolio_drawdown:
                healthy = False
            if request.observed_total_leverage is not None and request.observed_total_leverage > record.maximum_total_leverage:
                healthy = False
            if request.observed_liquidity_score is not None and request.observed_liquidity_score < record.minimum_liquidity_score:
                healthy = False
            record.consecutive_healthy_cycles = record.consecutive_healthy_cycles + 1 if healthy else 0
            record.state = DeploymentState.MONITORING if healthy else DeploymentState.ESCALATED
            record.deployment_evidence.extend(request.evidence_refs)
        elif action == "verify":
            self._require(record, DeploymentState.MONITORING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise CapitalDeploymentError("insufficient healthy monitoring cycles")
            record.state = DeploymentState.VERIFIED
        elif action == "escalate":
            record.state = DeploymentState.ESCALATED
        elif action == "suspend":
            self._require(record, DeploymentState.DEPLOYING, DeploymentState.MONITORING, DeploymentState.ESCALATED)
            record.state = DeploymentState.SUSPENDED
        elif action == "resume":
            self._require(record, DeploymentState.SUSPENDED)
            if record.risk_decision == RiskDecision.BLOCK:
                raise CapitalDeploymentError("Risk Brain blocks resume")
            record.state = DeploymentState.MONITORING
        elif action == "revoke":
            record.state = DeploymentState.REVOKED
        elif action == "archive":
            self._require(record, DeploymentState.VERIFIED, DeploymentState.REVOKED)
            record.state = DeploymentState.ARCHIVED

        record.updated_at = datetime.now(timezone.utc)
        self._emit(record, action, request.actor, before, record.state, request)
        return record

    def _refresh(self, record: CapitalDeploymentRecord) -> None:
        record.allocated_capital = sum(item.capital_amount for item in record.allocations)
        total_weight = sum(item.portfolio_weight for item in record.allocations)
        divisor = total_weight or 1
        record.weighted_confidence = sum(item.confidence * item.portfolio_weight for item in record.allocations) / divisor
        record.weighted_liquidity = sum(item.liquidity_score * item.portfolio_weight for item in record.allocations) / divisor
        record.projected_drawdown = sum(item.maximum_drawdown * item.portfolio_weight for item in record.allocations)
        record.total_leverage = sum(item.leverage * item.portfolio_weight for item in record.allocations)
        record.breached_allocations = sum(
            1
            for item in record.allocations
            if item.confidence < record.minimum_confidence
            or item.liquidity_score < record.minimum_liquidity_score
            or item.portfolio_weight > record.maximum_single_strategy_weight
            or item.capital_amount > item.capacity_limit
        )

    def _breached(self, record: CapitalDeploymentRecord) -> bool:
        return (
            record.breached_allocations > 0
            or record.projected_drawdown > record.maximum_portfolio_drawdown
            or record.total_leverage > record.maximum_total_leverage
            or record.allocated_capital > record.total_capital
        )

    @staticmethod
    def _require(record: CapitalDeploymentRecord, *states: DeploymentState) -> None:
        if record.state not in states:
            expected = ", ".join(item.value for item in states)
            raise CapitalDeploymentError(f"state must be one of: {expected}")

    def _emit(self, record, action, actor, before, after, request=None) -> None:
        details = {}
        if request is not None:
            details = {
                "note": request.note,
                "evidence_refs": request.evidence_refs,
                "healthy_cycles": record.consecutive_healthy_cycles,
            }
        self._audit.append(AuditEvent(
            record_id=record.record_id,
            workspace_id=record.workspace_id,
            action=action,
            actor=actor,
            from_state=before,
            to_state=after,
            details=details,
        ))


service = CapitalDeploymentService()
