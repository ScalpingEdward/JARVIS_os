from uuid import UUID

from .models import (
    AllocationLine,
    AllocationMode,
    AllocationPlan,
    AllocationRequest,
    AllocationStatus,
    RebalanceItem,
    RebalanceReport,
    RebalanceRequest,
)


class CapitalAllocationService:
    def __init__(self) -> None:
        self._plans: dict[UUID, AllocationPlan] = {}

    def reset(self) -> None:
        self._plans.clear()

    def status(self) -> AllocationStatus:
        return AllocationStatus(plans=len(self._plans))

    def create_plan(self, payload: AllocationRequest) -> AllocationPlan:
        active = [target for target in payload.targets if target.enabled]
        if not active:
            raise ValueError("At least one enabled allocation target is required")

        reserve_capital = round(payload.capital * payload.reserve_weight, 2)
        investable = round(payload.capital - reserve_capital, 2)
        mode_factor = {
            AllocationMode.defensive: 0.75,
            AllocationMode.balanced: 1.0,
            AllocationMode.growth: 1.25,
        }[payload.mode]

        raw_scores: list[float] = []
        warnings: list[str] = []
        for target in active:
            quality = max(0.01, (target.expected_return + 0.1) * target.confidence)
            risk_penalty = 1 + target.volatility + (target.drawdown * 2)
            score = max(0.001, quality * mode_factor / risk_penalty)
            if target.drawdown >= 0.08:
                score *= 0.35
                warnings.append(f"{target.name}: high drawdown reduces allocation")
            raw_scores.append(score)

        total_score = sum(raw_scores)
        initial_weights = [score / total_score * (1 - payload.reserve_weight) for score in raw_scores]
        bounded = [min(target.max_weight, max(target.min_weight, weight)) for target, weight in zip(active, initial_weights)]
        bounded_total = sum(bounded)
        scale = (1 - payload.reserve_weight) / bounded_total if bounded_total else 0
        recommended = [weight * scale for weight in bounded]

        lines: list[AllocationLine] = []
        for target, weight in zip(active, recommended):
            capital = round(payload.capital * weight, 2)
            risk_budget = round(capital * payload.max_total_risk * target.confidence, 2)
            drift = weight - target.current_weight
            action = "increase" if drift > 0.02 else "reduce" if drift < -0.02 else "hold"
            reasons = [
                f"confidence {target.confidence:.0%}",
                f"volatility {target.volatility:.0%}",
                f"drawdown {target.drawdown:.0%}",
            ]
            lines.append(
                AllocationLine(
                    target_id=target.id,
                    name=target.name,
                    target_type=target.target_type,
                    current_weight=round(target.current_weight, 4),
                    recommended_weight=round(weight, 4),
                    allocated_capital=capital,
                    risk_budget=risk_budget,
                    action=action,
                    reasons=reasons,
                )
            )

        plan = AllocationPlan(
            mode=payload.mode,
            total_capital=payload.capital,
            reserve_capital=reserve_capital,
            investable_capital=investable,
            lines=sorted(lines, key=lambda line: line.recommended_weight, reverse=True),
            warnings=sorted(set(warnings)),
            executive_recommendation=(
                "MASTER Brano, keep the reserve untouched and rebalance only after human review. "
                "Reduce exposure to targets with elevated drawdown before adding risk."
            ),
        )
        self._plans[plan.id] = plan
        return plan

    def list_plans(self) -> list[AllocationPlan]:
        return sorted(self._plans.values(), key=lambda plan: plan.created_at, reverse=True)

    def get_plan(self, plan_id: UUID) -> AllocationPlan | None:
        return self._plans.get(plan_id)

    def rebalance(self, payload: RebalanceRequest) -> RebalanceReport:
        plan = self._plans.get(payload.plan_id)
        if plan is None:
            raise KeyError("Allocation plan not found")
        items = []
        for line in plan.lines:
            drift = round(line.recommended_weight - line.current_weight, 4)
            if abs(drift) < payload.drift_threshold:
                recommendation = "hold"
            elif drift > 0:
                recommendation = "increase after approval"
            else:
                recommendation = "reduce after approval"
            items.append(
                RebalanceItem(
                    target_id=line.target_id,
                    name=line.name,
                    current_weight=line.current_weight,
                    target_weight=line.recommended_weight,
                    drift=drift,
                    recommendation=recommendation,
                )
            )
        return RebalanceReport(plan_id=plan.id, items=items)


capital_allocation_service = CapitalAllocationService()
