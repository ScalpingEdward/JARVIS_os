"""Strategy orchestrator service — coordinates accounts, strategies, and compliance."""

from __future__ import annotations

from ..accounts.models import AccountStatus
from ..accounts.service import account_registry_service
from ..strategies.models import MarketSnapshot
from ..strategies.service import strategy_service
from .models import AccountStrategyEvaluation, OrchestrationResult


class StrategyOrchestrator:
    """Orchestrates strategy evaluation across all accounts with compliance filtering."""

    def evaluate_all_accounts(self, snapshot: MarketSnapshot) -> OrchestrationResult:
        """Evaluate assigned strategies for all active accounts with compliance.

        Flow:
        1. Get all accounts from the registry
        2. For each account, get assigned strategies
        3. Evaluate only those strategies against the market snapshot
        4. Check account compliance (breached, suspended, etc.)
        5. Filter to only executable setups (valid + compliant)

        Returns:
            OrchestrationResult with per-account evaluations and summary stats.
        """
        accounts = account_registry_service.list_accounts()
        active_accounts = [a for a in accounts if a.status == AccountStatus.active]

        account_evaluations = []
        total_evaluations = 0
        total_valid_setups = 0
        total_executable_setups = 0

        for account in active_accounts:
            evaluation = self._evaluate_account(account, snapshot)
            account_evaluations.append(evaluation)
            total_evaluations += len(evaluation.strategy_results)
            total_valid_setups += len(evaluation.valid_setups)
            total_executable_setups += len(evaluation.executable_setups)

        return OrchestrationResult(
            symbol=snapshot.symbol,
            total_accounts=len(accounts),
            active_accounts=len(active_accounts),
            total_evaluations=total_evaluations,
            total_valid_setups=total_valid_setups,
            total_executable_setups=total_executable_setups,
            account_evaluations=account_evaluations,
        )

    def _evaluate_account(
        self, account, snapshot: MarketSnapshot
    ) -> AccountStrategyEvaluation:
        """Evaluate all assigned strategies for a single account."""
        # Get assigned strategy IDs
        assignments = account_registry_service.list_assignments(account.id)
        assigned_strategy_ids = [s.strategy_id for s in assignments]

        # Evaluate only the assigned strategies
        strategy_results = []
        for strategy_id in assigned_strategy_ids:
            result = strategy_service.evaluate_strategy(strategy_id, snapshot)
            strategy_results.append(result)

        # Filter to only valid setups (where setup is not None)
        valid_setups = [r for r in strategy_results if r.setup is not None]

        # Check compliance
        compliance = account_registry_service.compliance(account.id)
        compliance_ok = not compliance.breached and account.status == AccountStatus.active

        # Determine executable setups and blocked reason
        if compliance_ok:
            executable_setups = valid_setups
            blocked_reason = None
        else:
            executable_setups = []
            if compliance.breached:
                blocked_reason = f"Account breached: {', '.join(compliance.breach_reasons)}"
            elif account.status != AccountStatus.active:
                blocked_reason = f"Account status: {account.status.value}"
            else:
                blocked_reason = "Compliance check failed"

        return AccountStrategyEvaluation(
            account_id=account.id,
            login=account.login,
            account_type=account.account_type,
            status=account.status,
            assigned_strategies=assigned_strategy_ids,
            strategy_results=strategy_results,
            valid_setups=valid_setups,
            compliance_ok=compliance_ok,
            executable_setups=executable_setups,
            blocked_reason=blocked_reason,
        )


strategy_orchestrator = StrategyOrchestrator()
