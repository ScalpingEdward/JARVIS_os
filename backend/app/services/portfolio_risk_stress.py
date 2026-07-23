from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Dict, List
from uuid import uuid4

from app.schemas.portfolio_risk_stress import (
    PortfolioRiskAction,
    PortfolioRiskRecord,
    PortfolioRiskRecordCreate,
    PortfolioRiskScores,
    PortfolioRiskState,
)


@dataclass
class AuditEvent:
    record_id: str
    workspace_id: str
    actor: str
    action: str
    operation_id: str
    version: int


class PortfolioRiskStressService:
    def __init__(self) -> None:
        self._records: Dict[str, PortfolioRiskRecord] = {}
        self._source_keys: Dict[str, str] = {}
        self._operations: set[str] = set()
        self._audit: List[AuditEvent] = []

    def status(self) -> dict:
        return {
            "module": "portfolio-risk-stress",
            "version": "21.71",
            "records": len(self._records),
            "risk_brain_authority": "hard-block",
            "allocation_mutation_enabled": False,
            "execution_enabled": False,
        }

    def create(self, payload: PortfolioRiskRecordCreate) -> PortfolioRiskRecord:
        composite_key = f"{payload.workspace_id}:{payload.source_key}"
        if composite_key in self._source_keys:
            raise ValueError("duplicate source key within workspace")
        scores, flags = self._score(payload)
        state = PortfolioRiskState.REVIEW_REQUIRED if flags else PortfolioRiskState.SCORED
        record = PortfolioRiskRecord(
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

    def list(self, workspace_id: str) -> List[PortfolioRiskRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> PortfolioRiskRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError("record not found")
        return record

    def act(self, record_id: str, workspace_id: str, payload: PortfolioRiskAction, risk_blocked: bool = False) -> PortfolioRiskRecord:
        record = self.get(record_id, workspace_id)
        op_key = f"{workspace_id}:{payload.operation_id}"
        if op_key in self._operations:
            return record
        if risk_blocked and payload.action in {"approve", "activate", "monitor"}:
            record.state = PortfolioRiskState.BLOCKED
            record.risk_flags = sorted(set(record.risk_flags + ["risk-brain-hard-block"]))
        else:
            transitions = {
                "score": PortfolioRiskState.SCORED,
                "submit-review": PortfolioRiskState.REVIEW_REQUIRED,
                "approve": PortfolioRiskState.APPROVED,
                "activate": PortfolioRiskState.ACTIVE,
                "monitor": PortfolioRiskState.MONITORING,
                "suspend": PortfolioRiskState.SUSPENDED,
                "revoke": PortfolioRiskState.REVOKED,
                "archive": PortfolioRiskState.ARCHIVED,
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

    def _score(self, payload: PortfolioRiskRecordCreate) -> tuple[PortfolioRiskScores, List[str]]:
        items = payload.observations
        total_weight = sum(item.weight for item in items)
        normalized = [(item, item.weight / total_weight if total_weight else 0) for item in items]
        concentration = sum(weight * weight for _, weight in normalized) * 100
        expected_shortfall = sum(item.expected_shortfall_pct * weight for item, weight in normalized)
        stress_loss = sum(item.stress_loss_pct * weight for item, weight in normalized)
        drawdown = sum(item.drawdown_pct * weight for item, weight in normalized)
        liquidity = sum(min(item.liquidity_days / 20, 1) * weight for item, weight in normalized) * 100
        clusters: Dict[str, float] = {}
        for item, weight in normalized:
            clusters[item.correlation_cluster] = clusters.get(item.correlation_cluster, 0) + weight
        correlation_risk = max(clusters.values(), default=0) * 100
        confidence = mean(item.confidence * item.freshness for item in items)
        resilience = max(0, min(100, 100 - concentration * 0.35 - stress_loss * 2.5 - drawdown * 1.5 - liquidity * 0.3 - correlation_risk * 0.25))

        flags: List[str] = []
        if concentration > 35:
            flags.append("concentration-alert")
        if stress_loss > 12:
            flags.append("stress-breach")
        if drawdown > 15:
            flags.append("drawdown-alert")
        if liquidity > 55:
            flags.append("liquidity-risk-high")
        if correlation_risk > 60:
            flags.append("correlation-cluster-risk")
        if confidence < 0.6:
            flags.append("low-confidence")

        return PortfolioRiskScores(
            concentration_risk=round(concentration, 2),
            expected_shortfall_pct=round(expected_shortfall, 4),
            stress_loss_pct=round(stress_loss, 4),
            drawdown_pressure=round(drawdown, 4),
            liquidity_risk=round(liquidity, 2),
            correlation_risk=round(correlation_risk, 2),
            risk_resilience=round(resilience, 2),
            confidence=round(confidence, 4),
        ), flags


portfolio_risk_stress_service = PortfolioRiskStressService()
