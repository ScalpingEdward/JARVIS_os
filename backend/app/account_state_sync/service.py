from __future__ import annotations

from datetime import datetime, timezone

from ..accounts.models import AccountStateUpdate, AccountStatus
from ..accounts.service import AccountRegistryError, account_registry_service
from ..mt5_bridge.service import mt5_bridge_service
from .models import AccountSyncResult, SyncExecutionRequest, SyncExecutionSummary, SyncServiceStatus


class AccountStateSyncService:
    """Syncs broker account snapshots from MT5 terminals into the accounts registry.

    Matches registered accounts to MT5 terminals by (login, server), extracts the
    account balance/equity snapshot, and pushes it into the registry where
    compliance checks and breach-detection run automatically.
    """

    def __init__(self) -> None:
        self.last_sync_at: datetime | None = None
        self.last_sync_matched = 0
        self.last_sync_synced = 0

    def status(self) -> SyncServiceStatus:
        return SyncServiceStatus(
            last_sync_at=self.last_sync_at,
            last_sync_matched=self.last_sync_matched,
            last_sync_synced=self.last_sync_synced,
        )

    def sync(self, request: SyncExecutionRequest | None = None) -> SyncExecutionSummary:
        """Execute a sync run: match accounts to MT5 terminals and push state updates."""
        request = request or SyncExecutionRequest()

        # Fetch all registered accounts (or filter by account_ids if provided)
        all_accounts = account_registry_service.list_accounts()
        if request.account_ids:
            accounts = [a for a in all_accounts if a.id in request.account_ids]
        else:
            accounts = all_accounts

        # Filter by status unless force=True
        if not request.force:
            accounts = [a for a in accounts if a.status == AccountStatus.active]

        # Fetch all MT5 terminals and their snapshots
        mt5_terminals = mt5_bridge_service.list()

        # Build a lookup: (login_str, server) -> terminal_data
        terminal_map: dict[tuple[str, str], object] = {}
        for td in mt5_terminals:
            key = (str(td.terminal.account_login), td.terminal.server)
            terminal_map[key] = td

        results: list[AccountSyncResult] = []
        synced_count = 0
        matched_count = 0
        breaches_count = 0

        for account in accounts:
            result = AccountSyncResult(
                account_id=account.id,
                account_label=account.label,
                login=account.login,
                server=account.server,
                matched_terminal=False,
                synced=False,
            )

            # Try to find the matching MT5 terminal
            key = (account.login, account.server)
            terminal_data = terminal_map.get(key)

            if terminal_data is None:
                result.error = "No matching MT5 terminal found"
                results.append(result)
                continue

            result.matched_terminal = True
            matched_count += 1

            # Check if terminal has an account snapshot
            if terminal_data.account is None:
                result.error = "MT5 terminal has no account snapshot yet"
                results.append(result)
                continue

            # Extract balance and equity
            snapshot = terminal_data.account
            result.balance = snapshot.balance
            result.equity = snapshot.equity

            # Push the state update into the registry
            try:
                updated_account = account_registry_service.update_state(
                    account.id,
                    AccountStateUpdate(
                        balance=snapshot.balance,
                        equity=snapshot.equity,
                        # day_start_balance is optional; registry keeps existing if omitted
                    ),
                )
                result.synced = True
                synced_count += 1

                # Check if a breach was detected (status changed to breached)
                if updated_account.status == AccountStatus.breached and account.status != AccountStatus.breached:
                    result.breach_detected = True
                    breaches_count += 1

            except AccountRegistryError as exc:
                result.error = f"Registry update failed: {exc}"

            results.append(result)

        # Update internal stats
        self.last_sync_at = datetime.now(timezone.utc)
        self.last_sync_matched = matched_count
        self.last_sync_synced = synced_count

        return SyncExecutionSummary(
            total_accounts=len(accounts),
            matched_terminals=matched_count,
            synced=synced_count,
            failed=len(accounts) - synced_count,
            breaches_detected=breaches_count,
            results=results,
        )


account_state_sync_service = AccountStateSyncService()
