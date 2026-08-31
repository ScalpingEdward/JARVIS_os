"""Setup-submission service.

Bridges the strategy evaluation layer to the approval gate. For a given market
snapshot it evaluates every *executable* account's *enabled* strategies and, for
each resulting trading setup, records an in-memory approval request keyed by a
generated ``approval_request_id``.

Executable = account status is ``active``. Suspended, breached and passed
accounts are evaluated (they count toward ``total_accounts_evaluated``) but never
produce submitted setups — fail-closed: only an explicitly active account may
have setups sent to the approval gate.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.accounts.models import AccountStatus
from app.accounts.service import AccountRegistryService, account_registry_service
from app.strategies.service import (
    StrategyService,
    StrategyServiceError,
    strategy_service,
)

from .models import SetupSubmissionRequest, SetupSubmissionReport, SubmittedSetup


class SetupSubmissionService:
    """Turns orchestrator/strategy output into pending approval requests.

    Dependencies (the account registry and strategy service) are injectable so
    tests can supply isolated instances; production uses the shared singletons.
    Pending approval requests are held in memory, keyed by approval_request_id.
    """

    def __init__(
        self,
        account_registry: AccountRegistryService | None = None,
        strategies: StrategyService | None = None,
    ) -> None:
        self._accounts = account_registry or account_registry_service
        self._strategies = strategies or strategy_service
        self._approvals: dict[UUID, SubmittedSetup] = {}

    # -- submission -----------------------------------------------------------

    def submit(self, request: SetupSubmissionRequest) -> SetupSubmissionReport:
        """Evaluate accounts against the snapshot and submit executable setups.

        Does not execute trades — every produced setup is recorded as a pending
        approval request for a human operator to resolve downstream.
        """
        snapshot = request.snapshot
        symbol = request.symbol or snapshot.symbol

        accounts = self._accounts.list_accounts()
        if request.account_ids is not None:
            wanted = set(request.account_ids)
            accounts = [a for a in accounts if a.id in wanted]

        total_accounts_evaluated = len(accounts)
        executable_setups = 0
        submitted: list[SubmittedSetup] = []

        for account in accounts:
            # fail-closed: only active accounts may submit to the approval gate
            if account.status != AccountStatus.active:
                continue
            for assignment in self._accounts.list_assignments(account.id):
                if not assignment.enabled:
                    continue
                try:
                    result = self._strategies.evaluate_strategy(assignment.strategy_id, snapshot)
                except StrategyServiceError:
                    # unknown/removed strategy assigned to the account — skip it
                    continue
                if result.setup is None:
                    continue

                setup = result.setup
                executable_setups += 1
                submitted_setup = SubmittedSetup(
                    account_id=account.id,
                    login=account.login,
                    strategy_id=setup.strategy_id,
                    symbol=setup.symbol,
                    side=setup.side,
                    entry_price=setup.entry_price,
                    stop_loss=setup.stop_loss,
                    take_profits=setup.take_profits,
                    risk_reward=setup.risk_reward,
                    confidence=setup.confidence,
                    reasoning=setup.reasoning,
                    approval_request_id=uuid4(),
                )
                self._approvals[submitted_setup.approval_request_id] = submitted_setup
                submitted.append(submitted_setup)

        skipped_reason: str | None = None
        if total_accounts_evaluated == 0:
            skipped_reason = "Keine Konten entsprachen dem Filter."
        elif not submitted:
            skipped_reason = "Keine ausführbaren Setups für diesen Snapshot gefunden."

        return SetupSubmissionReport(
            symbol=symbol,
            total_accounts_evaluated=total_accounts_evaluated,
            total_executable_setups=executable_setups,
            total_submitted=len(submitted),
            submitted_setups=submitted,
            skipped_reason=skipped_reason,
        )

    # -- pending approvals ----------------------------------------------------

    def get_pending_approvals(self) -> list[SubmittedSetup]:
        """Return all pending (in-memory) approval requests, newest last."""
        return sorted(self._approvals.values(), key=lambda s: s.submitted_at)

    def get_approval(self, approval_request_id: UUID) -> SubmittedSetup | None:
        """Return a single pending approval request, or None if unknown."""
        return self._approvals.get(approval_request_id)

    def reset(self) -> None:
        """Clear all pending approval requests. Intended for tests/local resets."""
        self._approvals.clear()


setup_submission_service = SetupSubmissionService()
