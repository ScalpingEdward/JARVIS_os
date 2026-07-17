from collections import defaultdict
from uuid import UUID

from .models import (
    AccountAllocation,
    AccountState,
    AllocationCreate,
    AllocationPlan,
    RiskAllocationStatus,
)


class RiskAllocationService:
    def __init__(self) -> None:
        self._plans: dict[UUID, AllocationPlan] = {}

    def status(self) -> RiskAllocationStatus:
        return RiskAllocationStatus()

    def create(self, payload: AllocationCreate) -> AllocationPlan:
        enabled = [item for item in payload.accounts if item.enabled]
        total_balance = round(sum(item.balance for item in enabled), 2)
        portfolio_budget = round(total_balance * payload.portfolio_risk_budget_pct / 100, 2)
        remaining_portfolio = portfolio_budget
        group_usage: dict[str, float] = defaultdict(float)
        allocations: list[AccountAllocation] = []
        global_blockers: list[str] = []

        for account in enabled:
            blockers: list[str] = []
            buffer_factor = 1 - payload.safety_buffer_pct / 100
            dd_capacity = min(account.daily_drawdown_remaining, account.total_drawdown_remaining)
            capacity = round(max(0.0, dd_capacity * buffer_factor), 2)
            requested = round(account.balance * account.requested_risk_pct / 100, 2)
            account_cap = round(account.balance * payload.max_account_risk_pct / 100, 2)
            group_cap = round(total_balance * payload.max_correlation_group_risk_pct / 100, 2)
            remaining_group = max(0.0, group_cap - group_usage[account.correlation_group])
            allocated = round(min(requested, account_cap, capacity, remaining_group, remaining_portfolio), 2)

            if capacity <= 0:
                blockers.append("No drawdown capacity remains after the safety buffer.")
            if requested > account_cap:
                blockers.append("Requested risk exceeds the per-account limit.")
            if remaining_group <= 0:
                blockers.append("Correlation-group risk limit is exhausted.")
            if remaining_portfolio <= 0:
                blockers.append("Portfolio risk budget is exhausted.")

            if allocated <= 0:
                state = AccountState.BLOCKED
            elif blockers or allocated < requested:
                state = AccountState.CAUTION
            else:
                state = AccountState.ACTIVE

            group_usage[account.correlation_group] += allocated
            remaining_portfolio = round(max(0.0, remaining_portfolio - allocated), 2)
            allocations.append(
                AccountAllocation(
                    account_id=account.account_id,
                    provider=account.provider,
                    correlation_group=account.correlation_group,
                    state=state,
                    requested_risk_amount=requested,
                    allocated_risk_amount=allocated,
                    allocated_risk_pct=round(allocated / account.balance * 100, 4),
                    capacity_amount=capacity,
                    blockers=blockers,
                )
            )

        if not enabled:
            global_blockers.append("No enabled accounts are available for allocation.")
        blocked_count = sum(item.state == AccountState.BLOCKED for item in allocations)
        if blocked_count:
            global_blockers.append(f"{blocked_count} account(s) are blocked by risk limits.")
        allocated_total = round(sum(item.allocated_risk_amount for item in allocations), 2)
        recommendation = (
            "MASTER Brano: review every account and correlation group before manual approval."
            if allocations
            else "MASTER Brano: enable at least one account before creating a risk plan."
        )
        plan = AllocationPlan(
            name=payload.name.strip(),
            total_balance=total_balance,
            portfolio_risk_budget_amount=portfolio_budget,
            allocated_risk_amount=allocated_total,
            unused_risk_amount=round(max(0.0, portfolio_budget - allocated_total), 2),
            allocations=allocations,
            correlation_group_allocations={key: round(value, 2) for key, value in group_usage.items()},
            blockers=global_blockers,
            recommendation=recommendation,
        )
        self._plans[plan.id] = plan
        return plan

    def list_all(self) -> list[AllocationPlan]:
        return sorted(self._plans.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, plan_id: UUID) -> AllocationPlan | None:
        return self._plans.get(plan_id)


risk_allocation_service = RiskAllocationService()
