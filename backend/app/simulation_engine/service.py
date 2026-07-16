import math
import random
from datetime import datetime, timezone
from statistics import mean
from uuid import UUID

from .models import (
    SimulationCreate,
    SimulationKind,
    SimulationPlatformStatus,
    SimulationRecord,
    SimulationResult,
    SimulationState,
)


class SimulationService:
    def __init__(self) -> None:
        self._records: dict[UUID, SimulationRecord] = {}

    def reset(self) -> None:
        self._records.clear()

    def create(self, payload: SimulationCreate) -> SimulationRecord:
        record = SimulationRecord(**payload.model_dump())
        self._records[record.id] = record
        return record

    def list_all(self) -> list[SimulationRecord]:
        return sorted(self._records.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, simulation_id: UUID) -> SimulationRecord | None:
        return self._records.get(simulation_id)

    def run(self, simulation_id: UUID) -> SimulationRecord | None:
        record = self.get(simulation_id)
        if record is None:
            return None
        if record.state == SimulationState.running:
            raise ValueError("Simulation is already running")
        record.state = SimulationState.running
        record.updated_at = datetime.now(timezone.utc)
        try:
            if record.kind in {SimulationKind.trading, SimulationKind.monte_carlo}:
                record.result = self._run_trading(record)
            else:
                record.result = self._run_scenarios(record)
            record.state = SimulationState.completed
            record.error = None
        except Exception as exc:
            record.state = SimulationState.failed
            record.error = str(exc)
        record.updated_at = datetime.now(timezone.utc)
        return record

    def _run_scenarios(self, record: SimulationRecord) -> SimulationResult:
        scored = []
        for scenario in record.scenarios:
            score = scenario.probability * scenario.impact - scenario.risk * 0.35 - scenario.cost * 0.01
            scored.append((scenario, score))
        values = [score for _, score in scored]
        winner = max(scored, key=lambda item: item[1])[0]
        confidence = min(0.95, 0.45 + len(scored) * 0.05)
        return SimulationResult(
            expected_value=round(mean(values), 4),
            best_case=round(max(values), 4),
            worst_case=round(min(values), 4),
            confidence=confidence,
            uncertainty=round(1 - confidence, 4),
            probability_of_loss=round(sum(value < 0 for value in values) / len(values), 4),
            risk_of_ruin=0,
            recommended_scenario=winner.name,
            metrics={"scenario_count": len(scored)},
            limitations=["Scenario outputs depend on supplied probabilities and impacts.", "No production state is modified."],
        )

    def _run_trading(self, record: SimulationRecord) -> SimulationResult:
        trading = record.trading
        if trading is None:
            raise ValueError("Trading input is missing")
        rng = random.Random(record.seed)
        stop_distance = abs(trading.entry - trading.stop_loss)
        reward_distance = abs(trading.take_profit - trading.entry)
        rr = reward_distance / stop_distance
        balances = []
        max_drawdowns = []
        ruined = 0
        iterations = min(record.iterations, 100000)
        for _ in range(iterations):
            balance = trading.starting_balance
            peak = balance
            max_dd = 0.0
            for _ in range(trading.trades):
                risk_amount = balance * trading.risk_percent / 100
                balance += risk_amount * rr if rng.random() < trading.win_probability else -risk_amount
                peak = max(peak, balance)
                max_dd = max(max_dd, (peak - balance) / peak if peak else 1.0)
                if balance <= trading.starting_balance * 0.1:
                    ruined += 1
                    break
            balances.append(balance)
            max_drawdowns.append(max_dd)
        sorted_balances = sorted(balances)
        loss_probability = sum(value < trading.starting_balance for value in balances) / iterations
        expected_r = trading.win_probability * rr - (1 - trading.win_probability)
        return SimulationResult(
            expected_value=round(mean(balances), 2),
            best_case=round(sorted_balances[-1], 2),
            worst_case=round(sorted_balances[0], 2),
            confidence=round(min(0.99, 1 - 1 / math.sqrt(iterations)), 4),
            uncertainty=round(max(0.01, 1 / math.sqrt(iterations)), 4),
            probability_of_loss=round(loss_probability, 4),
            risk_of_ruin=round(ruined / iterations, 4),
            recommended_scenario="review" if expected_r <= 0 else "positive expectancy under assumptions",
            metrics={
                "risk_reward": round(rr, 4),
                "expected_r_per_trade": round(expected_r, 4),
                "median_final_balance": round(sorted_balances[len(sorted_balances) // 2], 2),
                "average_max_drawdown_percent": round(mean(max_drawdowns) * 100, 2),
                "iterations": iterations,
            },
            limitations=[
                "Uses independent Bernoulli outcomes and does not model slippage, spread, correlation or regime changes.",
                "Results are advisory and cannot place or modify orders.",
            ],
        )

    def status(self) -> SimulationPlatformStatus:
        records = self.list_all()
        return SimulationPlatformStatus(
            total=len(records),
            queued=sum(item.state == SimulationState.queued for item in records),
            running=sum(item.state == SimulationState.running for item in records),
            completed=sum(item.state == SimulationState.completed for item in records),
            failed=sum(item.state == SimulationState.failed for item in records),
        )


simulation_service = SimulationService()
