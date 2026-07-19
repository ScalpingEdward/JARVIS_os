from collections import defaultdict
from uuid import UUID

from .models import (
    AllocationLine,
    AuditRecord,
    FormationAssessment,
    FormationAssessmentCreate,
    FormationState,
    PayoutStatus,
    StatusResponse,
    UseCategory,
)


class ExecutivePropPayoutCapitalFormationService:
    def __init__(self) -> None:
        self._records: dict[str, list[FormationAssessment]] = defaultdict(list)
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: dict[str, list[AuditRecord]] = defaultdict(list)

    def create(self, payload: FormationAssessmentCreate) -> FormationAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate source_key for workspace")

        received = sum(p.payout_amount for p in payload.payouts if p.status == PayoutStatus.RECEIVED)
        expected = sum(p.payout_amount for p in payload.payouts if p.status in {
            PayoutStatus.EXPECTED, PayoutStatus.REQUESTED, PayoutStatus.CONFIRMED
        })
        nominal = sum(p.account_nominal_size for p in payload.payouts)
        reasons: list[str] = [
            "Prop account nominal size is tracked as external funded capacity, not owned capital.",
            "Only received payout cash is eligible for capital formation allocation.",
        ]

        if any(p.status == PayoutStatus.REJECTED for p in payload.payouts):
            reasons.append("At least one payout is rejected and excluded from allocation.")

        if received < payload.minimum_received_amount:
            state = FormationState.HOLD
            reasons.append("No sufficient received cash is available for allocation.")
        elif not payload.human_approval:
            state = FormationState.PLAN
            reasons.append("Human approval is required before any payout use becomes deployable.")
        else:
            state = FormationState.APPROVED
            reasons.append("Received payout allocation is approved for planning purposes.")

        policy = payload.policy
        category_percentages = [
            (UseCategory.TAX_RESERVE, policy.tax_reserve_pct, True),
            (UseCategory.EMERGENCY_RESERVE, policy.emergency_reserve_pct, True),
            (UseCategory.LIVING_COSTS, policy.living_costs_pct, False),
            (UseCategory.LIVE_TRADING_CAPITAL, policy.live_trading_capital_pct, False),
            (UseCategory.PROP_GROWTH, policy.prop_growth_pct, False),
            (UseCategory.LONG_TERM_INVESTING, policy.long_term_investing_pct, False),
        ]
        used_pct = sum(pct for _, pct, _ in category_percentages)
        if used_pct < 100:
            category_percentages.append((UseCategory.FREE_LIQUIDITY, 100 - used_pct, False))

        deployable = state == FormationState.APPROVED
        allocations = [
            AllocationLine(
                category=category,
                amount=round(received * percentage / 100, 2),
                percentage=percentage,
                deployable=deployable and received > 0,
                reason=("Protected reserve" if protected else "Requires approved downstream decision"),
            )
            for category, percentage, protected in category_percentages
        ]

        def amount_for(category: UseCategory) -> float:
            return next((line.amount for line in allocations if line.category == category), 0.0)

        assessment = FormationAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            received_cash=round(received, 2),
            expected_cash=round(expected, 2),
            prop_nominal_capital=round(nominal, 2),
            allocations=allocations,
            live_capital_contribution=amount_for(UseCategory.LIVE_TRADING_CAPITAL),
            prop_growth_budget=amount_for(UseCategory.PROP_GROWTH),
            protected_reserves=round(
                amount_for(UseCategory.TAX_RESERVE) + amount_for(UseCategory.EMERGENCY_RESERVE), 2
            ),
            free_liquidity=amount_for(UseCategory.FREE_LIQUIDITY),
            reasons=reasons,
        )
        self._records[payload.workspace_id].append(assessment)
        self._source_keys.add(key)
        self._audit[payload.workspace_id].append(AuditRecord(
            workspace_id=payload.workspace_id,
            assessment_id=assessment.assessment_id,
            actor_id=payload.actor_id,
            action=f"created:{state.value}",
        ))
        return assessment

    def list_assessments(self, workspace_id: str) -> list[FormationAssessment]:
        return list(self._records.get(workspace_id, []))

    def get(self, assessment_id: UUID, workspace_id: str) -> FormationAssessment | None:
        return next((r for r in self._records.get(workspace_id, []) if r.assessment_id == assessment_id), None)

    def status(self, workspace_id: str) -> StatusResponse:
        records = self._records.get(workspace_id, [])
        return StatusResponse(
            workspace_id=workspace_id,
            assessments=len(records),
            latest_state=records[-1].state if records else None,
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return list(self._audit.get(workspace_id, []))


executive_prop_payout_capital_formation_service = ExecutivePropPayoutCapitalFormationService()
