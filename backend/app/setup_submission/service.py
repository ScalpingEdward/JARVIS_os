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

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.accounts.models import AccountStatus
from app.accounts.service import AccountRegistryService, account_registry_service
from app.db import SessionLocal
from app.db_models import SubmittedSetupRow
from app.strategies.service import (
    StrategyService,
    StrategyServiceError,
    strategy_service,
)

from .models import (
    SetupDecisionRequest,
    SetupDecisionStatus,
    SetupSubmissionRequest,
    SetupSubmissionReport,
    SetupSubmissionStatus,
    SubmittedSetup,
)


class SetupSubmissionError(ValueError):
    pass


class SetupSubmissionService:
    """Turns orchestrator/strategy output into pending approval requests.

    Dependencies (the account registry and strategy service) are injectable so
    tests can supply isolated instances; production uses the shared singletons.

    Persisted via the same SQLAlchemy/SessionLocal infrastructure
    orchestrator.service already uses (see app/db.py, app/db_models.py) --
    previously an in-memory dict, silently emptied on every restart; found
    by an external test pass (finding #3). A fresh session is opened per
    call, matching orchestrator's own pattern, since this service is a
    module-level singleton used far outside any single FastAPI request
    (telegram_approvals, trade_risk_pipeline, tests all call it directly).
    """

    def __init__(
        self,
        account_registry: AccountRegistryService | None = None,
        strategies: StrategyService | None = None,
    ) -> None:
        self._accounts = account_registry or account_registry_service
        self._strategies = strategies or strategy_service

    @staticmethod
    def _to_row(setup: SubmittedSetup) -> SubmittedSetupRow:
        return SubmittedSetupRow(
            approval_request_id=str(setup.approval_request_id),
            account_id=str(setup.account_id),
            decision=setup.decision.value,
            submitted_at=setup.submitted_at,
            data=setup.model_dump_json(),
        )

    @staticmethod
    def _from_row(row: SubmittedSetupRow) -> SubmittedSetup:
        return SubmittedSetup.model_validate_json(row.data)

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
                submitted.append(submitted_setup)

        if submitted:
            with SessionLocal() as session:
                for submitted_setup in submitted:
                    session.merge(self._to_row(submitted_setup))
                session.commit()

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
        """Return only the setups still awaiting a decision, oldest first.

        Previously returned everything ever submitted regardless of
        decision -- the name and docstring promised "pending", the
        implementation delivered the full history. Harmless where the only
        caller already re-filtered client-side (telegram_approvals.
        notify_pending()), but GET /v1/setup-submission/pending returned
        this directly to the API with no such compensation: an operator
        checking "what still needs my attention" would have seen approved
        and rejected setups mixed in with no way to tell them apart at a
        glance. Use get_all() below for the full, undecided-and-decided
        history this used to silently return.
        """
        with SessionLocal() as session:
            rows = (
                session.query(SubmittedSetupRow)
                .filter(SubmittedSetupRow.decision == SetupDecisionStatus.pending.value)
                .order_by(SubmittedSetupRow.submitted_at)
                .all()
            )
        return [self._from_row(r) for r in rows]

    def get_all(self) -> list[SubmittedSetup]:
        """Every setup ever submitted, decided or not -- the full history
        get_pending_approvals() used to silently return under a misleading
        name. Oldest first, same ordering convention."""
        with SessionLocal() as session:
            rows = session.query(SubmittedSetupRow).order_by(SubmittedSetupRow.submitted_at).all()
        return [self._from_row(r) for r in rows]

    def status(self) -> SetupSubmissionStatus:
        """Capability health for the approval gate: how many setups are
        sitting in each decision state right now, and how long the oldest
        undecided one has been waiting."""
        all_setups = self.get_all()
        pending = [s for s in all_setups if s.decision == SetupDecisionStatus.pending]
        return SetupSubmissionStatus(
            total_ever_submitted=len(all_setups),
            pending=len(pending),
            approved=sum(1 for s in all_setups if s.decision == SetupDecisionStatus.approved),
            rejected=sum(1 for s in all_setups if s.decision == SetupDecisionStatus.rejected),
            oldest_pending_at=min((s.submitted_at for s in pending), default=None),
        )

    def get_approval(self, approval_request_id: UUID) -> SubmittedSetup | None:
        """Return a single pending approval request, or None if unknown."""
        with SessionLocal() as session:
            row = session.get(SubmittedSetupRow, str(approval_request_id))
        return self._from_row(row) if row else None

    def decide(self, approval_request_id: UUID, request: SetupDecisionRequest) -> SubmittedSetup:
        """Record a human's approve/reject decision. One-shot, fail-closed.

        This is the actual approval gate -- ``submit()`` only proposes which
        setups exist; nothing downstream (trade_risk_pipeline.assess() first
        among them) proceeds until a decision is recorded here as approved.
        A setup already decided cannot be decided again: the second call
        raises rather than silently overwriting who decided what, same
        one-shot discipline the rest of this codebase already uses (moderation
        decisions, research proposals, platform-strategy apply).
        """
        with SessionLocal() as session:
            row = session.get(SubmittedSetupRow, str(approval_request_id))
            if row is None:
                raise SetupSubmissionError(f"unknown approval_request_id {approval_request_id}")
            setup = self._from_row(row)
            if setup.decision != SetupDecisionStatus.pending:
                raise SetupSubmissionError(
                    f"approval_request_id {approval_request_id} was already "
                    f"{setup.decision.value} by {setup.decided_by} -- decisions are one-shot"
                )
            decided = setup.model_copy(update={
                "decision": request.decision,
                "decided_by": request.decided_by,
                "decided_at": datetime.now(timezone.utc),
                "decision_note": request.note,
            })
            row.decision = decided.decision.value
            row.data = decided.model_dump_json()
            session.commit()
        return decided

    def reset(self) -> None:
        """Clear all pending approval requests. Intended for tests/local resets."""
        with SessionLocal() as session:
            session.query(SubmittedSetupRow).delete()
            session.commit()


setup_submission_service = SetupSubmissionService()
