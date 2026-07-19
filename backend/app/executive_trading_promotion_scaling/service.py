from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AuditRecord,
    PromotionAssessment,
    PromotionInput,
    PromotionScores,
    PromotionState,
    PromotionStatusResponse,
    ScalingDimension,
    ScalingStep,
)


class ExecutiveTradingPromotionScalingService:
    def __init__(self) -> None:
        self._items: dict[UUID, PromotionAssessment] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(100.0, value)), 2)

    def assess(self, payload: PromotionInput) -> PromotionAssessment:
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.source_key == payload.source_key for item in self._items.values()):
                raise ValueError("A promotion assessment with this source key already exists in the workspace")

            blockers: list[str] = []
            reasons: list[str] = []
            mandatory_failed = [gate.name for gate in payload.gates if gate.mandatory and not gate.passed]
            sample_score = min(100.0, 100.0 * payload.sample_trades / payload.minimum_sample_trades)
            time_score = min(100.0, 100.0 * payload.stable_hours / payload.minimum_stable_hours)
            drawdown_headroom = self._clamp(100.0 * (1 - payload.max_drawdown_percent / payload.drawdown_limit_percent))
            readiness = self._clamp((sample_score + time_score + payload.overall_health) / 3)
            risk_capacity = self._clamp(payload.risk_stability * 0.65 + drawdown_headroom * 0.35)
            execution_capacity = self._clamp(payload.execution_stability)
            operational_capacity = self._clamp(payload.operational_stability)
            evidence_strength = self._clamp(payload.evidence_quality)
            confidence = self._clamp(
                readiness * 0.25
                + risk_capacity * 0.25
                + execution_capacity * 0.2
                + operational_capacity * 0.15
                + evidence_strength * 0.15
            )

            if payload.monitoring_state in {"blocked", "shadow", "reduce"}:
                blockers.append(f"Post-release monitoring state is {payload.monitoring_state}")
            if not payload.promotion_eligible:
                blockers.append("Post-release monitoring has not marked the strategy promotion-eligible")
            if payload.open_critical_issues:
                blockers.append("Critical issues remain open")
            if payload.max_drawdown_percent >= payload.drawdown_limit_percent:
                blockers.append("Drawdown limit has been reached")
            if payload.sample_trades < payload.minimum_sample_trades:
                blockers.append("Minimum observation-trade sample has not been reached")
            if payload.stable_hours < payload.minimum_stable_hours:
                blockers.append("Minimum stable operating period has not been reached")
            blockers.extend(f"Mandatory gate failed: {name}" for name in mandatory_failed)
            if not payload.human_approval:
                blockers.append("Human scaling approval is missing")

            approved_risk = payload.current_risk_multiplier
            approved_capital = payload.current_capital
            approved_symbols = payload.current_symbol_count
            approved_accounts = payload.current_account_count
            plan: list[ScalingStep] = []

            hard_block = payload.open_critical_issues > 0 or payload.monitoring_state == "blocked" or payload.max_drawdown_percent >= payload.drawdown_limit_percent
            if hard_block:
                state = PromotionState.blocked
                reasons.append("Scaling is blocked by a hard safety gate")
            elif blockers:
                state = PromotionState.hold
                reasons.append("Current allocation must be held until all promotion gates pass")
            else:
                requested_dimensions = []
                if payload.requested_risk_multiplier > payload.current_risk_multiplier:
                    requested_dimensions.append(ScalingDimension.risk)
                if payload.requested_capital > payload.current_capital:
                    requested_dimensions.append(ScalingDimension.capital)
                if payload.requested_symbol_count > payload.current_symbol_count:
                    requested_dimensions.append(ScalingDimension.symbols)
                if payload.requested_account_count > payload.current_account_count:
                    requested_dimensions.append(ScalingDimension.accounts)

                if not requested_dimensions:
                    state = PromotionState.eligible
                    reasons.append("All gates pass and the strategy is eligible for a future scaling request")
                else:
                    # One-step promotion prevents simultaneous uncontrolled expansion.
                    dimension = requested_dimensions[0]
                    if dimension == ScalingDimension.risk:
                        state = PromotionState.promote_risk
                        approved_risk = min(payload.requested_risk_multiplier, payload.current_risk_multiplier + 0.25, 1.0)
                        plan.append(ScalingStep(order=1, dimension=dimension, target=f"Risk multiplier {approved_risk:.2f}", verification="Reassess drift after the next observation window"))
                    elif dimension == ScalingDimension.capital:
                        state = PromotionState.promote_risk
                        approved_capital = min(payload.requested_capital, payload.current_capital * 1.5 if payload.current_capital else payload.requested_capital)
                        plan.append(ScalingStep(order=1, dimension=dimension, target=f"Capital {approved_capital:.2f}", verification="Confirm drawdown and liquidity remain within approved limits"))
                    elif dimension == ScalingDimension.symbols:
                        state = PromotionState.expand_symbols
                        approved_symbols = min(payload.requested_symbol_count, payload.current_symbol_count + 1)
                        plan.append(ScalingStep(order=1, dimension=dimension, target=f"Symbols {approved_symbols}", verification="Validate correlation and execution quality on the added symbol"))
                    else:
                        state = PromotionState.expand_accounts
                        approved_accounts = min(payload.requested_account_count, payload.current_account_count + 1)
                        plan.append(ScalingStep(order=1, dimension=dimension, target=f"Accounts {approved_accounts}", verification="Verify account isolation, copy consistency and aggregate exposure"))
                    reasons.append("Exactly one scaling dimension is approved per governance cycle")

            record = PromotionAssessment(
                workspace_id=payload.workspace_id,
                actor_id=payload.actor_id,
                source_key=payload.source_key,
                strategy_id=payload.strategy_id,
                state=state,
                scores=PromotionScores(
                    readiness=readiness,
                    risk_capacity=risk_capacity,
                    execution_capacity=execution_capacity,
                    operational_capacity=operational_capacity,
                    evidence_strength=evidence_strength,
                    scaling_confidence=confidence,
                ),
                approved_risk_multiplier=approved_risk,
                approved_capital=approved_capital,
                approved_symbol_count=approved_symbols,
                approved_account_count=approved_accounts,
                scaling_plan=plan,
                blockers=blockers,
                reasons=reasons,
                assessed_at=self._now(),
            )
            self._items[record.id] = record
            self._audit.append(AuditRecord(workspace_id=payload.workspace_id, action="trading-promotion-assessed", actor_id=payload.actor_id, assessment_id=record.id, details={"state": state.value, "confidence": confidence}, created_at=self._now()))
            return record

    def list_assessments(self, workspace_id: str) -> list[PromotionAssessment]:
        with self._lock:
            return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> PromotionAssessment | None:
        with self._lock:
            item = self._items.get(assessment_id)
            return item if item and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> PromotionStatusResponse:
        records = self.list_assessments(workspace_id)
        promoted_states = {PromotionState.promote_risk, PromotionState.expand_symbols, PromotionState.expand_accounts}
        return PromotionStatusResponse(
            assessments=len(records),
            eligible=sum(item.state == PromotionState.eligible for item in records),
            promoted=sum(item.state in promoted_states for item in records),
            held=sum(item.state == PromotionState.hold for item in records),
            blocked=sum(item.state == PromotionState.blocked for item in records),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_trading_promotion_scaling_service = ExecutiveTradingPromotionScalingService()
