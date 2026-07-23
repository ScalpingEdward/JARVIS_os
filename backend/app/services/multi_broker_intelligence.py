from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from uuid import uuid4

from app.schemas.multi_broker_intelligence import (
    BrokerObservation,
    BrokerRecommendation,
    MultiBrokerAction,
    MultiBrokerCreate,
    MultiBrokerRecord,
    MultiBrokerScores,
    MultiBrokerState,
)


class MultiBrokerConflictError(Exception):
    pass


class MultiBrokerNotFoundError(Exception):
    pass


class MultiBrokerPolicyError(Exception):
    pass


class MultiBrokerIntelligenceService:
    """Governed advisory intelligence for broker and venue routing.

    The service never submits orders, changes broker configuration, mutates
    routing tables or transfers funds. Risk Brain blocks are authoritative.
    """

    def __init__(self) -> None:
        self._records: Dict[str, MultiBrokerRecord] = {}
        self._payloads: Dict[str, MultiBrokerCreate] = {}
        self._source_index: Dict[Tuple[str, str], str] = {}
        self._operation_receipts: Dict[Tuple[str, str], dict] = {}
        self._audit: List[dict] = []
        self.risk_brain_blocked = False

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 6)

    @staticmethod
    def _weighted_average(items: List[Tuple[float, float]]) -> float:
        denominator = sum(weight for _, weight in items)
        if denominator <= 0:
            return 0.0
        return sum(value * weight for value, weight in items) / denominator

    def _broker_quality(
        self, observation: BrokerObservation, policy: MultiBrokerCreate
    ) -> Tuple[BrokerRecommendation, List[str], float]:
        latency_quality = self._clamp(1 - observation.p95_latency_ms / max(policy.max_latency_ms * 2, 1))
        spread_penalty = min((observation.realized_spread_bps + max(observation.slippage_bps, 0)) / 25, 1)
        execution_quality = self._clamp(
            0.28 * observation.fill_rate
            + 0.18 * (1 - observation.rejection_rate)
            + 0.16 * (1 - observation.partial_fill_rate)
            + 0.18 * latency_quality
            + 0.20 * (1 - spread_penalty)
        )
        reliability = self._clamp(
            0.55 * observation.uptime
            + 0.25 * (1 - observation.rejection_rate)
            + 0.20 * latency_quality
        )
        counterparty = self._clamp(
            0.60 * observation.counterparty_score + 0.40 * observation.regulatory_score
        )
        capacity = self._clamp(
            0.60 * (1 - observation.capacity_utilization)
            + 0.40 * observation.liquidity_score
        )
        confidence = self._clamp(observation.confidence * observation.freshness)
        composite = self._clamp(
            confidence
            * (
                0.35 * execution_quality
                + 0.22 * reliability
                + 0.20 * counterparty
                + 0.13 * capacity
                + 0.10 * observation.liquidity_score
            )
        )

        flags: List[str] = []
        if observation.p95_latency_ms > policy.max_latency_ms:
            flags.append(f"latency:{observation.broker_id}")
        if observation.fill_rate < policy.min_fill_rate:
            flags.append(f"fill-rate:{observation.broker_id}")
        if observation.rejection_rate > policy.max_rejection_rate:
            flags.append(f"rejection-rate:{observation.broker_id}")
        if observation.counterparty_score < policy.min_counterparty_score:
            flags.append(f"counterparty:{observation.broker_id}")
        if observation.capacity_utilization >= 0.90:
            flags.append(f"capacity:{observation.broker_id}")
        if observation.uptime < 0.995:
            flags.append(f"uptime:{observation.broker_id}")

        signal = "preferred"
        if any(flag.startswith("counterparty:") for flag in flags):
            signal = "suspend-routing"
        elif len(flags) >= 3:
            signal = "deprioritize"
        elif flags:
            signal = "review"

        return (
            BrokerRecommendation(
                broker_id=observation.broker_id,
                execution_quality_score=execution_quality,
                reliability_score=reliability,
                counterparty_resilience_score=counterparty,
                capacity_score=capacity,
                recommended_routing_weight=0,
                routing_signal=signal,
            ),
            flags,
            composite,
        )

    def _score(self, payload: MultiBrokerCreate) -> Tuple[MultiBrokerScores, List[BrokerRecommendation], List[str]]:
        raw: List[Tuple[BrokerRecommendation, float]] = []
        flags: List[str] = []
        observations = {item.broker_id: item for item in payload.observations}

        for observation in payload.observations:
            recommendation, broker_flags, composite = self._broker_quality(observation, payload)
            raw.append((recommendation, composite))
            flags.extend(broker_flags)

        eligible = [(recommendation, score) for recommendation, score in raw if recommendation.routing_signal != "suspend-routing"]
        total = sum(score for _, score in eligible)
        recommendations: List[BrokerRecommendation] = []
        remaining = 1.0

        for index, (recommendation, score) in enumerate(sorted(raw, key=lambda item: item[1], reverse=True)):
            if recommendation.routing_signal == "suspend-routing" or total <= 0:
                weight = 0.0
            else:
                proportional = score / total
                weight = min(proportional, payload.max_broker_weight, remaining)
                if index == len(raw) - 1 and remaining > 0:
                    weight = min(remaining, payload.max_broker_weight)
            remaining = max(0.0, remaining - weight)
            recommendations.append(recommendation.model_copy(update={"recommended_routing_weight": round(weight, 6)}))

        if remaining > 0.000001:
            flags.append("routing-capacity-unallocated")

        weighted = []
        for recommendation in recommendations:
            obs = observations[recommendation.broker_id]
            weight = max(recommendation.recommended_routing_weight, 0.000001)
            weighted.append((recommendation, obs, weight))

        aggregate_execution = self._weighted_average([(rec.execution_quality_score, weight) for rec, _, weight in weighted])
        reliability = self._weighted_average([(rec.reliability_score, weight) for rec, _, weight in weighted])
        liquidity = self._weighted_average([(obs.liquidity_score, weight) for _, obs, weight in weighted])
        counterparty = self._weighted_average([(rec.counterparty_resilience_score, weight) for rec, _, weight in weighted])
        regulatory = self._weighted_average([(obs.regulatory_score, weight) for _, obs, weight in weighted])
        capacity = self._weighted_average([(rec.capacity_score, weight) for rec, _, weight in weighted])
        max_weight = max((rec.recommended_routing_weight for rec in recommendations), default=1)
        concentration = self._clamp(1 - max_weight)
        confidence = self._weighted_average([(obs.confidence * obs.freshness, weight) for _, obs, weight in weighted])

        scores = MultiBrokerScores(
            aggregate_execution_quality=self._clamp(aggregate_execution),
            routing_resilience=self._clamp(0.55 * reliability + 0.45 * concentration),
            liquidity_quality=self._clamp(liquidity),
            counterparty_resilience=self._clamp(counterparty),
            regulatory_resilience=self._clamp(regulatory),
            capacity_headroom=self._clamp(capacity),
            concentration_quality=concentration,
            confidence=self._clamp(confidence),
        )
        return scores, recommendations, sorted(set(flags))

    def _state_from_flags(self, flags: List[str]) -> MultiBrokerState:
        if any(flag.startswith("counterparty:") for flag in flags):
            return MultiBrokerState.COUNTERPARTY_ALERT
        if any(flag.startswith("capacity:") for flag in flags):
            return MultiBrokerState.CAPACITY_ALERT
        if any(flag.startswith("latency:") for flag in flags):
            return MultiBrokerState.LATENCY_ALERT
        if any(flag.startswith(("fill-rate:", "rejection-rate:", "uptime:")) for flag in flags):
            return MultiBrokerState.EXECUTION_DEGRADATION
        return MultiBrokerState.SCORED

    def create(self, payload: MultiBrokerCreate) -> MultiBrokerRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_index:
            raise MultiBrokerConflictError("duplicate source key in workspace")
        scores, recommendations, flags = self._score(payload)
        record_id = str(uuid4())
        record = MultiBrokerRecord(
            record_id=record_id,
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=self._state_from_flags(flags),
            scores=scores,
            recommendations=recommendations,
            risk_flags=flags,
        )
        self._records[record_id] = record
        self._payloads[record_id] = payload
        self._source_index[source] = record_id
        self._audit_event(record, payload.requested_by, "create")
        return deepcopy(record)

    def list(self, workspace_id: str) -> List[MultiBrokerRecord]:
        return [deepcopy(record) for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> MultiBrokerRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise MultiBrokerNotFoundError("record not found")
        return deepcopy(record)

    def action(self, workspace_id: str, record_id: str, action: MultiBrokerAction) -> MultiBrokerRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise MultiBrokerNotFoundError("record not found")
        receipt_key = (workspace_id, action.operation_id)
        if receipt_key in self._operation_receipts:
            raise MultiBrokerConflictError("operation already processed")
        if action.action in {"approve", "activate"} and self.risk_brain_blocked:
            raise MultiBrokerPolicyError("Risk Brain hard block is active")

        transitions = {
            "score": self._state_from_flags(record.risk_flags),
            "submit-review": MultiBrokerState.REVIEW_REQUIRED,
            "approve": MultiBrokerState.APPROVED,
            "activate": MultiBrokerState.ACTIVE,
            "monitor": MultiBrokerState.MONITORING,
            "suspend": MultiBrokerState.SUSPENDED,
            "revoke": MultiBrokerState.REVOKED,
            "archive": MultiBrokerState.ARCHIVED,
        }
        if action.action == "activate" and record.state != MultiBrokerState.APPROVED:
            raise MultiBrokerPolicyError("human approval required before activation")
        if action.action == "approve" and record.state != MultiBrokerState.REVIEW_REQUIRED:
            raise MultiBrokerPolicyError("record must be submitted for review")

        update = {"state": transitions[action.action], "version": record.version + 1}
        if action.action == "approve":
            update["approved_by"] = action.actor
        updated = record.model_copy(update=update)
        self._records[record_id] = updated
        self._operation_receipts[receipt_key] = {"record_id": record_id, "action": action.action}
        self._audit_event(updated, action.actor, action.action, action.reason)
        return deepcopy(updated)

    def audit(self, workspace_id: str) -> List[dict]:
        return [deepcopy(item) for item in self._audit if item["workspace_id"] == workspace_id]

    def status(self) -> dict:
        return {
            "module": "multi-broker-intelligence-governance",
            "version": "v21.75",
            "governance_only": True,
            "broker_configuration_mutation_enabled": False,
            "routing_mutation_enabled": False,
            "fund_movement_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
            "risk_brain_blocked": self.risk_brain_blocked,
        }

    def _audit_event(self, record: MultiBrokerRecord, actor: str, action: str, reason: str | None = None) -> None:
        self._audit.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "workspace_id": record.workspace_id,
                "record_id": record.record_id,
                "version": record.version,
                "actor": actor,
                "action": action,
                "state": record.state.value,
                "reason": reason,
            }
        )


multi_broker_intelligence_service = MultiBrokerIntelligenceService()
