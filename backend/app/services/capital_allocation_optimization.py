from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean
from typing import Dict, List
from uuid import uuid4

from app.schemas.capital_allocation_optimization import (
    AllocationAction,
    AllocationRecord,
    AllocationRecordCreate,
    AllocationScores,
    AllocationState,
)


@dataclass
class AuditEvent:
    record_id: str
    workspace_id: str
    actor: str
    action: str
    operation_id: str
    version: int


class CapitalAllocationOptimizationService:
    def __init__(self) -> None:
        self._records: Dict[str, AllocationRecord] = {}
        self._source_keys: Dict[str, str] = {}
        self._operations: set[str] = set()
        self._audit: List[AuditEvent] = []

    def status(self) -> dict:
        return {
            "module": "capital-allocation-optimization",
            "version": "21.72",
            "records": len(self._records),
            "risk_brain_authority": "hard-block",
            "allocation_mutation_enabled": False,
            "execution_enabled": False,
        }

    def create(self, payload: AllocationRecordCreate) -> AllocationRecord:
        composite_key = f"{payload.workspace_id}:{payload.source_key}"
        if composite_key in self._source_keys:
            raise ValueError("duplicate source key within workspace")

        scores, flags = self._score(payload)
        state = AllocationState.REVIEW_REQUIRED if flags else AllocationState.SCORED
        record = AllocationRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            scores=scores,
            risk_flags=flags,
        )
        self._records[record.record_id] = record
        self._source_keys[composite_key] = record.record_id
        self._audit.append(AuditEvent(record.record_id, record.workspace_id, payload.requested_by, "create", composite_key, 1))
        return record

    def list(self, workspace_id: str) -> List[AllocationRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> AllocationRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError("record not found")
        return record

    def act(self, record_id: str, workspace_id: str, payload: AllocationAction, risk_blocked: bool = False) -> AllocationRecord:
        record = self.get(record_id, workspace_id)
        op_key = f"{workspace_id}:{payload.operation_id}"
        if op_key in self._operations:
            return record
        if risk_blocked and payload.action in {"approve", "activate", "monitor"}:
            record.state = AllocationState.BLOCKED
            record.risk_flags = sorted(set(record.risk_flags + ["risk-brain-hard-block"]))
        else:
            transitions = {
                "score": AllocationState.SCORED,
                "submit-review": AllocationState.REVIEW_REQUIRED,
                "approve": AllocationState.APPROVED,
                "activate": AllocationState.ACTIVE,
                "monitor": AllocationState.MONITORING,
                "suspend": AllocationState.SUSPENDED,
                "revoke": AllocationState.REVOKED,
                "archive": AllocationState.ARCHIVED,
            }
            if payload.action == "approve":
                record.approved_by = payload.actor
            record.state = transitions[payload.action]
        record.version += 1
        self._operations.add(op_key)
        self._audit.append(AuditEvent(record.record_id, workspace_id, payload.actor, payload.action, payload.operation_id, record.version))
        return record

    def audit(self, workspace_id: str) -> List[dict]:
        return [event.__dict__ for event in self._audit if event.workspace_id == workspace_id]

    def _score(self, payload: AllocationRecordCreate) -> tuple[AllocationScores, List[str]]:
        proposed_total = sum(item.proposed_weight for item in payload.candidates)
        normalized = proposed_total if proposed_total > 0 else 1
        weights = [item.proposed_weight / normalized for item in payload.candidates]
        expected_return = sum(w * item.expected_return for w, item in zip(weights, payload.candidates))
        volatility = sqrt(sum((w * item.expected_volatility) ** 2 for w, item in zip(weights, payload.candidates)))
        shortfall = sum(w * item.expected_shortfall for w, item in zip(weights, payload.candidates))
        liquidity = sum(w * item.liquidity_score for w, item in zip(weights, payload.candidates))
        turnover = sum(abs(item.proposed_weight - item.current_weight) for item in payload.candidates) / 2
        concentration = sum(w * w for w in weights)
        diversification = max(0, min(100, (1 - concentration) * 125))
        efficiency = expected_return / volatility if volatility else 0
        confidence = mean(item.confidence * item.freshness for item in payload.candidates)

        violations = 0
        flags: List[str] = []
        if abs(proposed_total - 1) > 0.01:
            flags.append("weight-sum-invalid")
            violations += 1
        if any(item.proposed_weight > payload.max_single_weight for item in payload.candidates):
            flags.append("concentration-alert")
            violations += 1
        if turnover > payload.max_turnover:
            flags.append("turnover-limit-breach")
            violations += 1
        if liquidity < payload.min_liquidity_score:
            flags.append("liquidity-floor-breach")
            violations += 1
        if efficiency < 0.5:
            flags.append("efficiency-decay")
        if confidence < 0.6:
            flags.append("low-confidence")
        compliance = max(0, 100 - violations * 25)

        return AllocationScores(
            expected_portfolio_return=round(expected_return, 6),
            expected_portfolio_volatility=round(volatility, 6),
            expected_shortfall=round(shortfall, 6),
            risk_adjusted_efficiency=round(efficiency, 4),
            diversification_score=round(diversification, 2),
            liquidity_score=round(liquidity, 2),
            turnover=round(turnover, 4),
            constraint_compliance=round(compliance, 2),
            confidence=round(confidence, 4),
        ), flags


capital_allocation_service = CapitalAllocationOptimizationService()
