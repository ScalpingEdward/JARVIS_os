from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Dict, List
from uuid import uuid4

from app.schemas.portfolio_performance_attribution import (
    AttributionAction,
    AttributionRecord,
    AttributionRecordCreate,
    AttributionScores,
    AttributionState,
)


@dataclass
class AuditEvent:
    record_id: str
    workspace_id: str
    actor: str
    action: str
    operation_id: str
    version: int


class PortfolioAttributionService:
    def __init__(self) -> None:
        self._records: Dict[str, AttributionRecord] = {}
        self._source_keys: Dict[str, str] = {}
        self._operations: set[str] = set()
        self._audit: List[AuditEvent] = []

    def status(self) -> dict:
        return {
            "module": "portfolio-performance-attribution",
            "version": "21.70",
            "records": len(self._records),
            "risk_brain_authority": "hard-block",
            "allocation_mutation_enabled": False,
        }

    def create(self, payload: AttributionRecordCreate) -> AttributionRecord:
        composite_key = f"{payload.workspace_id}:{payload.source_key}"
        if composite_key in self._source_keys:
            raise ValueError("duplicate source key within workspace")
        scores, flags = self._score(payload)
        state = AttributionState.REVIEW_REQUIRED if flags else AttributionState.SCORED
        record = AttributionRecord(
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

    def list(self, workspace_id: str) -> List[AttributionRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> AttributionRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError("record not found")
        return record

    def act(self, record_id: str, workspace_id: str, payload: AttributionAction, risk_blocked: bool = False) -> AttributionRecord:
        record = self.get(record_id, workspace_id)
        op_key = f"{workspace_id}:{payload.operation_id}"
        if op_key in self._operations:
            return record
        if risk_blocked and payload.action in {"approve", "activate", "monitor"}:
            record.state = AttributionState.BLOCKED
            record.risk_flags = sorted(set(record.risk_flags + ["risk-brain-hard-block"]))
        else:
            transitions = {
                "score": AttributionState.SCORED,
                "submit-review": AttributionState.REVIEW_REQUIRED,
                "approve": AttributionState.APPROVED,
                "activate": AttributionState.ACTIVE,
                "monitor": AttributionState.MONITORING,
                "suspend": AttributionState.SUSPENDED,
                "revoke": AttributionState.REVOKED,
                "archive": AttributionState.ARCHIVED,
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

    def _score(self, payload: AttributionRecordCreate) -> tuple[AttributionScores, List[str]]:
        weighted_returns: List[float] = []
        weighted_benchmarks: List[float] = []
        allocation: List[float] = []
        selection: List[float] = []
        costs: List[float] = []
        risk_efficiencies: List[float] = []
        drawdowns: List[float] = []
        confidences: List[float] = []
        active_returns: List[float] = []

        for item in payload.observations:
            active = item.portfolio_return - item.benchmark_return
            weighted_returns.append(item.weight * item.portfolio_return)
            weighted_benchmarks.append(item.weight * item.benchmark_return)
            allocation.append(item.weight * item.benchmark_return)
            selection.append(item.weight * active)
            costs.append(item.weight * item.transaction_cost_bps)
            risk_efficiencies.append(active / item.active_risk if item.active_risk > 0 else active)
            drawdowns.append(item.drawdown)
            confidences.append(item.confidence * item.freshness)
            active_returns.append(active)

        total_return = sum(weighted_returns)
        benchmark_return = sum(weighted_benchmarks)
        active_return = total_return - benchmark_return
        dispersion = pstdev(active_returns) if len(active_returns) > 1 else 0
        risk_efficiency = mean(risk_efficiencies)
        resilience = max(0, min(100, 100 - mean(drawdowns) * 100))
        persistence = max(0, min(100, 50 + active_return * 1000 - dispersion * 500))
        confidence = mean(confidences)

        flags: List[str] = []
        if active_return < -0.01:
            flags.append("benchmark-divergence")
        if risk_efficiency < -0.25:
            flags.append("risk-drift")
        if persistence < 40:
            flags.append("alpha-decay")
        if mean(drawdowns) > 0.15:
            flags.append("drawdown-stress")
        if confidence < 0.6:
            flags.append("low-confidence")

        return AttributionScores(
            total_return=round(total_return, 6),
            benchmark_return=round(benchmark_return, 6),
            active_return=round(active_return, 6),
            allocation_effect=round(sum(allocation), 6),
            selection_effect=round(sum(selection), 6),
            cost_drag_bps=round(sum(costs), 4),
            risk_efficiency=round(risk_efficiency, 4),
            drawdown_resilience=round(resilience, 2),
            alpha_persistence=round(persistence, 2),
            confidence=round(confidence, 4),
        ), flags


portfolio_attribution_service = PortfolioAttributionService()
