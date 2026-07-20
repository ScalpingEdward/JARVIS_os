from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    RebalancingAssessment,
    RebalancingAssessmentCreate,
    RebalancingScores,
    RebalancingState,
    RebalancingStatusResponse,
    RotationAction,
    RotationLine,
)


class ExecutiveLiveRebalancingStrategyRotationService:
    def __init__(self) -> None:
        self._records: dict[UUID, RebalancingAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: RebalancingAssessmentCreate) -> RebalancingAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate rebalancing source key")

        total = round(payload.owned_live_capital, 2)
        hard_block = not payload.risk_brain_clear or total <= 0
        reasons: list[str] = []
        if not payload.risk_brain_clear:
            reasons.append("Risk Brain is not clear for Live portfolio rotation")
        if total <= 0:
            reasons.append("No owned Live capital is available")

        max_cycle_rotation = round(total * payload.policy.max_rotation_share_per_cycle, 2)
        remaining_rotation = max_cycle_rotation
        raw_lines: list[dict] = []

        for position in payload.positions:
            item_reasons: list[str] = []
            action = RotationAction.hold
            desired = position.target_capital

            weak_quality = (
                position.performance_score < payload.policy.minimum_performance_score
                or position.stability_score < payload.policy.minimum_stability_score
            )
            excessive_risk = position.current_risk_share > payload.policy.max_strategy_risk_share
            excessive_drawdown = position.drawdown_share > payload.policy.max_strategy_drawdown_share

            if not position.enabled:
                action = RotationAction.pause
                desired = 0.0
                item_reasons.append("Strategy is disabled")
            elif excessive_drawdown:
                action = RotationAction.pause
                desired = 0.0
                item_reasons.append("Strategy drawdown exceeds policy")
            elif weak_quality or excessive_risk:
                action = RotationAction.reduce
                desired = min(position.target_capital, position.current_capital * 0.5)
                if weak_quality:
                    item_reasons.append("Performance or stability score is below policy")
                if excessive_risk:
                    item_reasons.append("Strategy risk share exceeds policy")
            elif position.target_capital > position.current_capital:
                action = RotationAction.increase
                item_reasons.append("Strategy quality supports a controlled increase")
            elif position.target_capital < position.current_capital:
                action = RotationAction.reduce
                item_reasons.append("Current capital exceeds target allocation")

            requested_change = round(desired - position.current_capital, 2)
            raw_lines.append(
                {
                    "position": position,
                    "action": action,
                    "desired": max(0.0, round(desired, 2)),
                    "requested_change": requested_change,
                    "reasons": item_reasons,
                }
            )

        released = round(
            sum(max(0.0, -item["requested_change"]) for item in raw_lines), 2
        )
        increase_budget = min(max_cycle_rotation, released)

        lines: list[RotationLine] = []
        planned_rotation = 0.0
        for item in raw_lines:
            position = item["position"]
            change = item["requested_change"]
            action = item["action"]
            item_reasons = item["reasons"]

            if change > 0:
                allowed = min(change, increase_budget, remaining_rotation)
                if allowed < payload.policy.minimum_rotation_amount:
                    allowed = 0.0
                    action = RotationAction.hold
                    item_reasons.append("Increase is below minimum rotation amount or budget")
                change = round(allowed, 2)
                increase_budget = round(max(0.0, increase_budget - change), 2)
            else:
                change = round(max(-remaining_rotation, change), 2)

            remaining_rotation = round(max(0.0, remaining_rotation - abs(change)), 2)
            recommended = round(position.current_capital + change, 2)
            if action in {RotationAction.increase, RotationAction.reduce, RotationAction.pause} and change != 0:
                planned_rotation = round(planned_rotation + abs(change), 2)

            deployable = payload.human_approved and not hard_block and change != 0
            if change != 0 and not payload.human_approved:
                item_reasons.append("Human approval is required before rebalancing")

            lines.append(
                RotationLine(
                    strategy_id=position.strategy_id,
                    broker_id=position.broker_id,
                    symbol=position.symbol.upper(),
                    current_capital=round(position.current_capital, 2),
                    recommended_capital=recommended,
                    recommended_change=change,
                    action=action,
                    deployable=deployable,
                    reasons=item_reasons,
                )
            )

        approved_rotation = planned_rotation if payload.human_approved and not hard_block else 0.0
        actionable = [line for line in lines if line.recommended_change != 0]

        if hard_block:
            state = RebalancingState.blocked
        elif not payload.human_approved:
            state = RebalancingState.hold
            reasons.append("Rebalancing plan requires human approval")
        elif not actionable:
            state = RebalancingState.monitor
            reasons.append("Portfolio remains within rotation policy")
        elif any(line.action == RotationAction.increase for line in actionable):
            state = RebalancingState.rotation_ready
            reasons.append("Capital can be rotated toward stronger Live strategies")
        else:
            state = RebalancingState.rebalance
            reasons.append("Risk reduction or strategy pause is recommended")

        avg_quality = round(
            sum((p.performance_score + p.stability_score) / 2 for p in payload.positions)
            / len(payload.positions)
        )
        worst_drawdown = max((p.drawdown_share for p in payload.positions), default=0.0)
        drawdown_safety = max(0, round(100 * (1 - worst_drawdown)))
        rotation_efficiency = min(100, round(100 * planned_rotation / max(1.0, max_cycle_rotation)))
        target_total = sum(p.target_capital for p in payload.positions)
        capital_alignment = max(0, round(100 * (1 - abs(target_total - total) / max(1.0, total))))
        confidence = round((avg_quality + drawdown_safety + rotation_efficiency + capital_alignment) / 4)

        record = RebalancingAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            state=state,
            owned_live_capital=total,
            planned_rotation_capital=planned_rotation,
            approved_rotation_capital=approved_rotation,
            rotation_lines=lines,
            scores=RebalancingScores(
                strategy_quality=avg_quality,
                drawdown_safety=drawdown_safety,
                rotation_efficiency=rotation_efficiency,
                capital_alignment=capital_alignment,
                rebalancing_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(
            AuditRecord(
                workspace_id=record.workspace_id,
                assessment_id=record.id,
                actor_id=record.actor_id,
                action="live-rebalancing-strategy-rotation-assessed",
            )
        )
        return record

    def list_assessments(self, workspace_id: str) -> list[RebalancingAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> RebalancingAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> RebalancingStatusResponse:
        items = self.list_assessments(workspace_id)
        return RebalancingStatusResponse(
            workspace_id=workspace_id,
            assessments=len(items),
            latest_state=items[-1].state if items else None,
        )

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_live_rebalancing_strategy_rotation_service = (
    ExecutiveLiveRebalancingStrategyRotationService()
)
