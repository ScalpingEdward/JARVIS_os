from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Dict, List
from uuid import uuid4

from app.schemas.execution_quality_transaction_cost import (
    ExecutionAction,
    ExecutionRecord,
    ExecutionRecordCreate,
    ExecutionScores,
    ExecutionState,
)


@dataclass
class AuditEvent:
    record_id: str
    workspace_id: str
    actor: str
    action: str
    operation_id: str
    version: int


class ExecutionQualityService:
    def __init__(self) -> None:
        self._records: Dict[str, ExecutionRecord] = {}
        self._source_keys: Dict[str, str] = {}
        self._operations: set[str] = set()
        self._audit: List[AuditEvent] = []

    def status(self) -> dict:
        return {
            "module": "execution-quality-transaction-cost",
            "version": "21.69",
            "records": len(self._records),
            "risk_brain_authority": "hard-block",
            "execution_enabled": False,
        }

    def create(self, payload: ExecutionRecordCreate) -> ExecutionRecord:
        composite_key = f"{payload.workspace_id}:{payload.source_key}"
        if composite_key in self._source_keys:
            raise ValueError("duplicate source key within workspace")

        scores, flags = self._score(payload)
        state = ExecutionState.REVIEW_REQUIRED if flags else ExecutionState.SCORED
        record = ExecutionRecord(
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

    def list(self, workspace_id: str) -> List[ExecutionRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> ExecutionRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError("record not found")
        return record

    def act(self, record_id: str, workspace_id: str, payload: ExecutionAction, risk_blocked: bool = False) -> ExecutionRecord:
        record = self.get(record_id, workspace_id)
        op_key = f"{workspace_id}:{payload.operation_id}"
        if op_key in self._operations:
            return record
        if risk_blocked and payload.action in {"approve", "activate", "monitor"}:
            record.state = ExecutionState.BLOCKED
            record.risk_flags = sorted(set(record.risk_flags + ["risk-brain-hard-block"]))
        else:
            transitions = {
                "score": ExecutionState.SCORED,
                "submit-review": ExecutionState.REVIEW_REQUIRED,
                "approve": ExecutionState.APPROVED,
                "activate": ExecutionState.ACTIVE,
                "monitor": ExecutionState.MONITORING,
                "suspend": ExecutionState.SUSPENDED,
                "revoke": ExecutionState.REVOKED,
                "archive": ExecutionState.ARCHIVED,
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

    def _score(self, payload: ExecutionRecordCreate) -> tuple[ExecutionScores, List[str]]:
        shortfalls: List[float] = []
        slippages: List[float] = []
        fill_rates: List[float] = []
        fees: List[float] = []
        venue_components: List[float] = []
        confidences: List[float] = []

        for item in payload.observations:
            direction = 1 if item.side == "buy" else -1
            shortfall = direction * (item.average_fill_price - item.arrival_price) / item.arrival_price * 10_000
            benchmark = item.benchmark_price or item.arrival_price
            slippage = direction * (item.average_fill_price - benchmark) / benchmark * 10_000
            fill_rate = min(item.filled_quantity / item.requested_quantity, 1)
            latency_penalty = min(item.latency_ms / 5_000, 1)
            venue_quality = max(0, 100 - max(shortfall, 0) * 1.5 - latency_penalty * 25 - (1 - fill_rate) * 45)
            shortfalls.append(shortfall)
            slippages.append(slippage)
            fill_rates.append(fill_rate)
            fees.append(item.explicit_fees_bps)
            venue_components.append(venue_quality)
            confidences.append(item.confidence * item.freshness)

        dispersion = pstdev(shortfalls) if len(shortfalls) > 1 else 0
        avg_shortfall = mean(shortfalls)
        avg_slippage = mean(slippages)
        avg_fee = mean(fees)
        avg_fill = mean(fill_rates)
        avg_venue = mean(venue_components)
        confidence = mean(confidences)
        quality = max(0, min(100, 100 - max(avg_shortfall, 0) * 2 - avg_fee - (1 - avg_fill) * 50 - dispersion))
        stability = max(0, min(100, 100 - dispersion * 3))

        flags: List[str] = []
        if avg_shortfall > 15:
            flags.append("implementation-shortfall-high")
        if avg_slippage > 10:
            flags.append("slippage-alert")
        if avg_fill < 0.9:
            flags.append("fill-rate-low")
        if avg_venue < 60:
            flags.append("venue-degradation")
        if confidence < 0.6:
            flags.append("low-confidence")

        return ExecutionScores(
            implementation_shortfall_bps=round(avg_shortfall, 4),
            realized_slippage_bps=round(avg_slippage, 4),
            explicit_cost_bps=round(avg_fee, 4),
            fill_rate=round(avg_fill, 4),
            execution_quality=round(quality, 2),
            venue_quality=round(avg_venue, 2),
            cost_stability=round(stability, 2),
            confidence=round(confidence, 4),
        ), flags


execution_quality_service = ExecutionQualityService()
