from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Dict, List
from uuid import uuid4

from app.schemas.real_time_portfolio_ai_brain import (
    PortfolioBrainAction,
    PortfolioBrainCreate,
    PortfolioBrainRecommendation,
    PortfolioBrainRecord,
    PortfolioBrainScores,
    PortfolioBrainState,
)


class PortfolioBrainError(ValueError):
    pass


class RealTimePortfolioAIBrainService:
    def __init__(self) -> None:
        self._records: Dict[str, PortfolioBrainRecord] = {}
        self._source_keys: Dict[str, str] = {}
        self._operation_receipts: set[str] = set()
        self._audit: List[dict] = []
        self._lock = RLock()

    @staticmethod
    def _weighted_average(values: List[tuple[float, float]]) -> float:
        denominator = sum(weight for _, weight in values)
        if denominator <= 0:
            return 0.0
        return sum(value * weight for value, weight in values) / denominator

    def _score(self, payload: PortfolioBrainCreate) -> PortfolioBrainScores:
        weighted = [
            (signal.direction, signal.confidence * signal.freshness)
            for signal in payload.signals
        ]
        conviction = abs(self._weighted_average(weighted))
        severity = self._weighted_average([
            (signal.severity, signal.confidence * signal.freshness)
            for signal in payload.signals
        ])
        conflict = max(0.0, 1.0 - conviction)
        blocked_ratio = sum(1 for signal in payload.signals if signal.risk_blocked) / len(payload.signals)
        infrastructure = [s for s in payload.signals if s.domain in {"broker", "exchange", "infrastructure"}]
        infrastructure_readiness = 1.0 - self._weighted_average([
            (s.severity, s.confidence * s.freshness) for s in infrastructure
        ]) if infrastructure else 1.0
        risk_pressure = min(1.0, 0.35 * severity + 0.25 * payload.current_drawdown + 0.20 * blocked_ratio + 0.20 * (1 - payload.liquidity_buffer))
        regime_signals = [s for s in payload.signals if s.domain in {"macro", "regime", "cross-asset"}]
        regime_stability = 1.0 - self._weighted_average([
            (s.severity, s.confidence * s.freshness) for s in regime_signals
        ]) if regime_signals else 0.75
        signal_coherence = max(0.0, 1.0 - conflict)
        decision_confidence = max(0.0, min(1.0, 0.25 * conviction + 0.20 * signal_coherence + 0.20 * regime_stability + 0.20 * infrastructure_readiness + 0.15 * payload.liquidity_buffer))
        return PortfolioBrainScores(
            conviction=round(conviction, 6),
            risk_pressure=round(risk_pressure, 6),
            regime_stability=round(regime_stability, 6),
            signal_coherence=round(signal_coherence, 6),
            infrastructure_readiness=round(infrastructure_readiness, 6),
            liquidity_resilience=round(payload.liquidity_buffer, 6),
            decision_confidence=round(decision_confidence, 6),
        )

    def _recommend(self, payload: PortfolioBrainCreate, scores: PortfolioBrainScores) -> tuple[List[PortfolioBrainRecommendation], List[str]]:
        flags: List[str] = []
        recommendations: List[PortfolioBrainRecommendation] = []
        if any(signal.risk_blocked for signal in payload.signals):
            flags.append("risk-brain-hard-block")
            recommendations.append(PortfolioBrainRecommendation(action="hold-risk", priority=5, rationale="One or more governed intelligence domains are hard blocked."))
        if scores.risk_pressure >= payload.max_risk_pressure:
            flags.append("risk-pressure")
            recommendations.append(PortfolioBrainRecommendation(action="reduce-risk-review", priority=5, rationale="Composite risk pressure exceeds the governed threshold.", advisory_parameters={"suggested_exposure_multiplier": 0.5}))
        if scores.regime_stability < 0.45:
            flags.append("regime-shift")
            recommendations.append(PortfolioBrainRecommendation(action="regime-review", priority=4, rationale="Regime stability is below the review floor."))
        if scores.signal_coherence < 0.40:
            flags.append("signal-conflict")
            recommendations.append(PortfolioBrainRecommendation(action="defer-allocation-change", priority=4, rationale="Cross-domain signals are materially conflicting."))
        if scores.infrastructure_readiness < 0.60:
            flags.append("infrastructure-degraded")
            recommendations.append(PortfolioBrainRecommendation(action="routing-health-review", priority=5, rationale="Execution infrastructure readiness is degraded."))
        if not recommendations:
            recommendations.append(PortfolioBrainRecommendation(action="maintain-and-monitor", priority=2, rationale="No governed threshold breach is present."))
        return recommendations, flags

    def create(self, payload: PortfolioBrainCreate) -> PortfolioBrainRecord:
        with self._lock:
            scoped_key = f"{payload.workspace_id}:{payload.source_key}"
            if scoped_key in self._source_keys:
                raise PortfolioBrainError("duplicate source key")
            scores = self._score(payload)
            recommendations, flags = self._recommend(payload, scores)
            state = PortfolioBrainState.BLOCKED if "risk-brain-hard-block" in flags else PortfolioBrainState.SCORED
            record = PortfolioBrainRecord(record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key, state=state, scores=scores, recommendations=recommendations, risk_flags=flags)
            self._records[record.record_id] = record
            self._source_keys[scoped_key] = record.record_id
            self._write_audit(record, "created", payload.requested_by)
            return deepcopy(record)

    def list(self, workspace_id: str) -> List[PortfolioBrainRecord]:
        return [deepcopy(record) for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> PortfolioBrainRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise PortfolioBrainError("record not found")
        return deepcopy(record)

    def act(self, workspace_id: str, record_id: str, command: PortfolioBrainAction) -> PortfolioBrainRecord:
        with self._lock:
            if command.operation_id in self._operation_receipts:
                raise PortfolioBrainError("operation replay detected")
            record = self._records.get(record_id)
            if not record or record.workspace_id != workspace_id:
                raise PortfolioBrainError("record not found")
            transitions = {
                "score": PortfolioBrainState.SCORED,
                "submit-review": PortfolioBrainState.REVIEW_REQUIRED,
                "approve": PortfolioBrainState.APPROVED,
                "activate": PortfolioBrainState.ACTIVE,
                "monitor": PortfolioBrainState.MONITORING,
                "suspend": PortfolioBrainState.SUSPENDED,
                "revoke": PortfolioBrainState.REVOKED,
                "archive": PortfolioBrainState.ARCHIVED,
            }
            if command.action in {"approve", "activate"} and "risk-brain-hard-block" in record.risk_flags:
                raise PortfolioBrainError("Risk Brain hard block is authoritative")
            if command.action == "activate" and not record.approved_by:
                raise PortfolioBrainError("human approval required")
            record.state = transitions[command.action]
            if command.action == "approve":
                record.approved_by = command.actor
            record.version += 1
            self._operation_receipts.add(command.operation_id)
            self._write_audit(record, command.action, command.actor, command.reason)
            return deepcopy(record)

    def audit(self, workspace_id: str) -> List[dict]:
        return [deepcopy(entry) for entry in self._audit if entry["workspace_id"] == workspace_id]

    def _write_audit(self, record: PortfolioBrainRecord, action: str, actor: str, reason: str | None = None) -> None:
        self._audit.append({"record_id": record.record_id, "workspace_id": record.workspace_id, "action": action, "actor": actor, "reason": reason, "state": record.state.value, "version": record.version, "timestamp": datetime.now(timezone.utc).isoformat()})


real_time_portfolio_ai_brain_service = RealTimePortfolioAIBrainService()
