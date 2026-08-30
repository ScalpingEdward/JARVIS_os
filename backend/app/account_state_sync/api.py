from __future__ import annotations

from fastapi import APIRouter

from .models import SyncExecutionRequest, SyncExecutionSummary, SyncServiceStatus
from .service import account_state_sync_service

router = APIRouter(prefix="/v1/account-state-sync", tags=["account-state-sync"])


@router.get("/status", response_model=SyncServiceStatus)
def status() -> SyncServiceStatus:
    """Check the account-state-sync service status and last sync stats."""
    return account_state_sync_service.status()


@router.post("/sync", response_model=SyncExecutionSummary)
def sync(request: SyncExecutionRequest | None = None) -> SyncExecutionSummary:
    """Sync broker state from MT5 terminals into the accounts registry.

    Matches each registered account to its MT5 terminal by (login, server),
    extracts the balance/equity snapshot, and pushes it into the registry
    where compliance checks and breach-detection run automatically.

    By default syncs only active accounts; set force=True to include
    suspended/breached accounts.
    """
    return account_state_sync_service.sync(request)
