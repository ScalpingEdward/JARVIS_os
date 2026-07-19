from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    TreasuryAllocationLine,
    TreasuryAssessment,
    TreasuryAssessmentCreate,
    TreasuryScores,
    TreasuryState,
    TreasuryStatusResponse,
    WealthBucket,
)


class ExecutiveTreasuryWealthGovernanceService:
    def __init__(self) -> None:
        self._records: dict[UUID, TreasuryAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: TreasuryAssessmentCreate) -> TreasuryAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate treasury source key")

        owned = round(payload.owned_cash + payload.received_prop_payout_cash, 2)
        tax_gap = max(0.0, payload.policy.minimum_tax_reserve - payload.existing_tax_reserve)
        emergency_target = max(
            payload.policy.minimum_emergency_reserve,
            payload.policy.monthly_living_costs * payload.policy.minimum_runway_months,
        )
        emergency_gap = max(0.0, emergency_target - payload.existing_emergency_reserve)
        protected = round(tax_gap + emergency_gap, 2)
        after_reserves = max(0.0, owned - protected)

        max_withdrawal = owned * payload.policy.max_single_withdrawal_share
        sustainable_withdrawal = min(payload.requested_withdrawal, max_withdrawal, after_reserves)
        approved_withdrawal = round(sustainable_withdrawal if payload.human_approved else 0.0, 2)
        growth_capital = round(max(0.0, after_reserves - approved_withdrawal), 2)

        live_target = round(min(growth_capital * 0.5, owned * payload.policy.max_live_trading_share), 2)
        investment_target = round(min(growth_capital - live_target, owned * payload.policy.max_investment_share), 2)
        opportunity_target = round(max(0.0, growth_capital - live_target - investment_target), 2)

        hard_reserve_gap = tax_gap > 0 or emergency_gap > 0
        reasons: list[str] = []
        if hard_reserve_gap:
            state = TreasuryState.preserve
            reasons.append("Protected tax or emergency reserves are below policy")
        elif payload.requested_withdrawal > max_withdrawal:
            state = TreasuryState.withdrawal_review
            reasons.append("Requested withdrawal exceeds the single-withdrawal policy limit")
        elif not payload.human_approved:
            state = TreasuryState.balanced
            reasons.append("Plan calculated but human approval is required")
        elif growth_capital > 0:
            state = TreasuryState.growth_ready
            reasons.append("Protected reserves are satisfied and owned growth capital is available")
        else:
            state = TreasuryState.balanced
            reasons.append("No surplus growth capital is currently available")

        deployable = payload.human_approved and not hard_reserve_gap
        lines = [
            TreasuryAllocationLine(bucket=WealthBucket.tax_reserve, current_amount=payload.existing_tax_reserve, target_amount=payload.policy.minimum_tax_reserve, recommended_change=round(tax_gap, 2), deployable=payload.human_approved, rationale="Protect tax obligations before discretionary allocation"),
            TreasuryAllocationLine(bucket=WealthBucket.emergency_reserve, current_amount=payload.existing_emergency_reserve, target_amount=round(emergency_target, 2), recommended_change=round(emergency_gap, 2), deployable=payload.human_approved, rationale="Maintain the configured living-cost runway"),
            TreasuryAllocationLine(bucket=WealthBucket.live_trading, current_amount=payload.existing_live_trading_capital, target_amount=round(payload.existing_live_trading_capital + live_target, 2), recommended_change=live_target, deployable=deployable, rationale="Allocate only owned surplus capital to Live trading"),
            TreasuryAllocationLine(bucket=WealthBucket.long_term_investing, current_amount=payload.existing_long_term_investments, target_amount=round(payload.existing_long_term_investments + investment_target, 2), recommended_change=investment_target, deployable=deployable, rationale="Build diversified long-term owned assets"),
            TreasuryAllocationLine(bucket=WealthBucket.opportunity_cash, current_amount=0, target_amount=opportunity_target, recommended_change=opportunity_target, deployable=deployable, rationale="Preserve flexible liquidity after reserves and growth allocations"),
        ]

        reserve_score = min(100, round(100 * min(1.0, (payload.existing_tax_reserve + payload.existing_emergency_reserve + min(owned, protected)) / max(1.0, payload.policy.minimum_tax_reserve + emergency_target))))
        liquidity_score = min(100, round(100 * owned / max(1.0, emergency_target + payload.policy.minimum_tax_reserve)))
        withdrawal_score = 100 if payload.requested_withdrawal == 0 else max(0, round(100 * sustainable_withdrawal / payload.requested_withdrawal))
        investment_score = min(100, round(100 * growth_capital / max(1.0, owned)))
        stability = round((reserve_score + liquidity_score + withdrawal_score) / 3)
        confidence = round((reserve_score + liquidity_score + investment_score + withdrawal_score + stability) / 5)

        record = TreasuryAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            state=state,
            owned_capital=owned,
            excluded_prop_nominal_capital=payload.prop_nominal_capital,
            protected_capital=protected,
            growth_capital=growth_capital,
            approved_withdrawal=approved_withdrawal,
            allocation_lines=lines,
            scores=TreasuryScores(
                liquidity_health=liquidity_score,
                reserve_adequacy=reserve_score,
                investment_capacity=investment_score,
                withdrawal_sustainability=withdrawal_score,
                treasury_stability=stability,
                wealth_formation_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, assessment_id=record.id, actor_id=record.actor_id, action="treasury-assessment-created"))
        return record

    def list(self, workspace_id: str) -> list[TreasuryAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> TreasuryAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> TreasuryStatusResponse:
        items = self.list(workspace_id)
        return TreasuryStatusResponse(workspace_id=workspace_id, assessments=len(items), latest_state=items[-1].state if items else None)

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_treasury_wealth_governance_service = ExecutiveTreasuryWealthGovernanceService()
