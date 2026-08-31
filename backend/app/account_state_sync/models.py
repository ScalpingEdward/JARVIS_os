from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


class AccountSyncResult(BaseModel):
    """The outcome of syncing a single account's broker state into the registry."""

    account_id: UUID
    account_label: str
    login: str
    server: str
    matched_terminal: bool
    synced: bool
    balance: float | None = None
    equity: float | None = None
    breach_detected: bool = False
    error: str | None = None


class SyncExecutionRequest(BaseModel):
    """Request to sync all accounts or a specific subset."""

    account_ids: list[UUID] | None = Field(
        default=None,
        description="If set, only sync these accounts; otherwise sync all active accounts",
    )
    force: bool = Field(
        default=False,
        description="If True, sync suspended/breached accounts too (default: active only)",
    )


class SyncExecutionSummary(BaseModel):
    """Summary of a sync run across all matched accounts."""

    total_accounts: int
    matched_terminals: int
    synced: int
    failed: int
    breaches_detected: int
    results: list[AccountSyncResult] = Field(default_factory=list)
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SyncServiceStatus(BaseModel):
    """Current state of the account-state-sync service."""

    module: str = "account-state-sync"
    version: str = "1.0"
    accounts_registry_available: bool = True
    mt5_bridge_available: bool = True
    last_sync_at: datetime | None = None
    last_sync_matched: int = 0
    last_sync_synced: int = 0
