from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Dict, List
from uuid import uuid4

from app.schemas.scenario_simulation_rebalancing import (
    ScenarioAction,
    ScenarioRecord,
    ScenarioRecordCreate,
    ScenarioScores,
    ScenarioState,
)


@dataclass
class AuditEvent:
    record_id: str
    workspace_id: str
    actor: str
    action: str
    operation_id: str
    version: int


class ScenarioSimulationService:
    def __init__(self) -> None:
        self._records: Dict[str, ScenarioRecord] = {}
        self._source_keys: Dict[str, str] = {}
        self._operations: set[str] = set()
        self._audit: List[AuditEvent] = []

    def status(self) -> dict:
        return {
            "module": "scenario-simulation-rebalancing",
            "version": "21.73",
            "records": len(self._records),
            "risk_brain_authority": "hard-block",
            "allocation_mutation_enabled": False,
            "execution_enabled": False,
        }

    def create(self, payload: ScenarioRecordCreate) -> ScenarioRecord:
        composite_key = f"{payload.workspace_id}:{payload.source_key}"
        if composite_key in self._source_keys:
            raise ValueError("duplicate source key within workspace")

        scores, recommended, flags = self._score(payload)
        state = ScenarioState.REVIEW_REQUIRED if flags else ScenarioState.SCORED
        record = ScenarioRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            scores=scores,
            recommended_weights=recommended,
            risk_flags=flags,
        )
        self._records[record.record_id] = record
        self._source_keys[composite_key] = record.record_id
        self._audit.append(
            AuditEvent(record.record_id, record.workspace_id, payload.requested_by, "create", composite_key, 1)
        )
        return record

    def list(self, workspace_id: str) -> List[ScenarioRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> ScenarioRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError("record not found")
        return record

    def act(
        self,
        record_id: str,
        workspace_id: str,
        payload: ScenarioAction,
        risk_blocked: bool = False,
    ) -> ScenarioRecord:
        record = self.get(record_id, workspace_id)
        op_key = f"{workspace_id}:{payload.operation_id}"
        if op_key in self._operations:
            return record

        if risk_blocked and payload.action in {"approve", "activate", "monitor"}:
            record.state = ScenarioState.BLOCKED
            record.risk_flags = sorted(set(record.risk_flags + ["risk-brain-hard-block"]))
        else:
            transitions = {
                "score": ScenarioState.SCORED,
                "submit-review": ScenarioState.REVIEW_REQUIRED,
                "approve": ScenarioState.APPROVED,
                "activate": ScenarioState.ACTIVE,
                "monitor": ScenarioState.MONITORING,
                "suspend": ScenarioState.SUSPENDED,
                "revoke": ScenarioState.REVOKED,
                "archive": ScenarioState.ARCHIVED,
            }
            if payload.action == "approve":
                record.approved_by = payload.actor
            record.state = transitions[payload.action]

        record.version += 1
        self._operations.add(op_key)
        self._audit.append(
            AuditEvent(record.record_id, workspace_id, payload.actor, payload.action, payload.operation_id, record.version)
        )
        return record

    def audit(self, workspace_id: str) -> List[dict]:
        return [event.__dict__ for event in self._audit if event.workspace_id == workspace_id]

    def _score(self, payload: ScenarioRecordCreate) -> tuple[ScenarioScores, dict[str, float], List[str]]:
        scenario_losses: List[float] = []
        weighted_losses: List[float] = []
        liquidity_components: List[float] = []
        correlation_components: List[float] = []
        confidence_components: List[float] = []

        for shock in payload.shocks:
            portfolio_impact = 0.0
            for sleeve in payload.sleeves:
                sensitivity = sleeve.factor_sensitivities.get(shock.factor, 0.0)
                liquidity_penalty = max(shock.liquidity_multiplier - 1, 0) * (100 - sleeve.liquidity_score) / 100
                volatility_penalty = max(shock.volatility_multiplier - 1, 0) * sleeve.volatility_pct
                correlation_penalty = max(shock.correlation_shift, 0) * sleeve.volatility_pct
                sleeve_impact = sleeve.current_weight * (
                    sensitivity * shock.shock_pct - liquidity_penalty - volatility_penalty - correlation_penalty
                )
                portfolio_impact += sleeve_impact

            loss = max(-portfolio_impact, 0)
            scenario_losses.append(loss)
            weighted_losses.append(loss * shock.probability)
            liquidity_components.append(max(0, 100 - max(shock.liquidity_multiplier - 1, 0) * 30))
            correlation_components.append(max(0, 100 - max(shock.correlation_shift, 0) * 80))
            confidence_components.append(shock.confidence * shock.freshness)

        expected_loss = mean(scenario_losses)
        tail_loss = max(scenario_losses)
        probability_weighted_loss = sum(weighted_losses)
        turnover = sum(abs(item.target_weight - item.current_weight) for item in payload.sleeves) / 2
        pressure = min(100, max(0, tail_loss / payload.max_acceptable_loss_pct * 100))
        liquidity_resilience = mean(liquidity_components)
        correlation_resilience = mean(correlation_components)
        resilience = max(
            0,
            min(
                100,
                100
                - tail_loss / payload.max_acceptable_loss_pct * 55
                - turnover / payload.max_turnover_pct * 20
                - (100 - liquidity_resilience) * 0.15
                - (100 - correlation_resilience) * 0.1,
            ),
        )
        confidence = mean(confidence_components)

        recommended: dict[str, float] = {}
        total_adjusted = 0.0
        raw_weights: dict[str, float] = {}
        for sleeve in payload.sleeves:
            vulnerability = 0.0
            for shock in payload.shocks:
                sensitivity = abs(sleeve.factor_sensitivities.get(shock.factor, 0.0))
                vulnerability += sensitivity * abs(shock.shock_pct) * shock.probability
            adjustment = max(0.25, 1 - vulnerability - (100 - sleeve.liquidity_score) / 500)
            raw = sleeve.target_weight * adjustment
            raw_weights[sleeve.name] = raw
            total_adjusted += raw

        for name, raw in raw_weights.items():
            recommended[name] = round(raw / total_adjusted, 6) if total_adjusted else 0.0

        flags: List[str] = []
        if tail_loss > payload.max_acceptable_loss_pct:
            flags.append("scenario-breach")
        if turnover > payload.max_turnover_pct:
            flags.append("turnover-limit-breach")
        if pressure >= 75:
            flags.append("rebalance-pressure")
        if resilience < 60:
            flags.append("resilience-decay")
        if liquidity_resilience < 60:
            flags.append("liquidity-resilience-low")
        if confidence < 0.6:
            flags.append("low-confidence")

        return (
            ScenarioScores(
                expected_scenario_loss_pct=round(expected_loss, 6),
                tail_scenario_loss_pct=round(tail_loss, 6),
                probability_weighted_loss_pct=round(probability_weighted_loss, 6),
                rebalancing_pressure=round(pressure, 2),
                turnover_requirement_pct=round(turnover, 6),
                liquidity_resilience=round(liquidity_resilience, 2),
                correlation_resilience=round(correlation_resilience, 2),
                portfolio_resilience=round(resilience, 2),
                recommendation_confidence=round(confidence, 4),
            ),
            recommended,
            flags,
        )


scenario_simulation_service = ScenarioSimulationService()
