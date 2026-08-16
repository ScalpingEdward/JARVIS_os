from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.content.auron_instagram_registry_calendar_v21_540 import InstagramContentRegistryCalendar


class MetaReadHealthError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderHealthSnapshot:
    account_id: str
    provider_account_ref: str
    username: str
    token_state: str
    permission_state: str
    granted_permissions: tuple[str, ...]
    provider_reachable: bool
    observed_at: str
    external_calls_made: int = 0


@dataclass(frozen=True)
class AccountVerification:
    account_id: str
    state: str
    identity_match: bool
    token_healthy: bool
    permissions_healthy: bool
    provider_reachable: bool
    blockers: tuple[str, ...]
    observed_at: str
    external_calls_made: int = 0


class MetaInstagramReadSource(Protocol):
    """Read-only provider boundary for later Meta Graph integration."""

    def read_health(self, provider_account_ref: str) -> ProviderHealthSnapshot: ...


class InMemoryMetaInstagramReadSource:
    """Deterministic C3 source used for tests and local dry-run; no network calls."""

    def __init__(self, snapshots: dict[str, ProviderHealthSnapshot]) -> None:
        self.snapshots = snapshots

    def read_health(self, provider_account_ref: str) -> ProviderHealthSnapshot:
        try:
            return self.snapshots[provider_account_ref]
        except KeyError as exc:
            raise MetaReadHealthError('provider account not found in read source') from exc


class MetaInstagramReadHealthAdapter:
    """C3 provider identity/token/permission health verification.

    This adapter is read-only. It stores health/verification evidence, never stores
    access-token secrets, and exposes no publish/write method.
    """

    def __init__(self, db_path: str | Path, registry: InstagramContentRegistryCalendar,
                 source: MetaInstagramReadSource,
                 required_permissions: tuple[str, ...] = ('account.read',)) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.source = source
        self.required_permissions = tuple(dict.fromkeys(p.strip() for p in required_permissions if p.strip()))
        if not self.required_permissions:
            raise MetaReadHealthError('at least one required read permission must be configured')
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS meta_provider_health (
                account_id TEXT PRIMARY KEY,
                provider_account_ref TEXT NOT NULL,
                username TEXT NOT NULL,
                token_state TEXT NOT NULL,
                permission_state TEXT NOT NULL,
                granted_permissions_csv TEXT NOT NULL,
                provider_reachable INTEGER NOT NULL,
                observed_at TEXT NOT NULL,
                external_calls_made INTEGER NOT NULL
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS meta_account_verification (
                account_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                identity_match INTEGER NOT NULL,
                token_healthy INTEGER NOT NULL,
                permissions_healthy INTEGER NOT NULL,
                provider_reachable INTEGER NOT NULL,
                blockers_csv TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                external_calls_made INTEGER NOT NULL
            )''')

    def sync_and_verify(self, account_id: str) -> AccountVerification:
        account = self.registry.get_account(account_id)
        if account is None:
            raise MetaReadHealthError('Instagram account is not registered')
        if account.status != 'active':
            return self._persist_verification(AccountVerification(
                account_id, 'blocked', False, False, False, False,
                ('instagram-account-not-active',), self._now(), 0,
            ))
        if not account.provider_account_ref:
            return self._persist_verification(AccountVerification(
                account_id, 'blocked', False, False, False, False,
                ('provider-account-ref-missing',), self._now(), 0,
            ))

        snapshot = self.source.read_health(account.provider_account_ref)
        self._persist_health(snapshot)

        blockers: list[str] = []
        identity_match = (
            snapshot.provider_account_ref == account.provider_account_ref
            and snapshot.username.strip().lstrip('@').lower() == account.handle.strip().lstrip('@').lower()
        )
        if not identity_match:
            blockers.append('provider-identity-mismatch')

        token_healthy = snapshot.token_state == 'healthy'
        if not token_healthy:
            blockers.append('provider-token-unhealthy')

        granted = {permission.strip() for permission in snapshot.granted_permissions}
        missing_permissions = [p for p in self.required_permissions if p not in granted]
        permissions_healthy = snapshot.permission_state == 'healthy' and not missing_permissions
        if snapshot.permission_state != 'healthy':
            blockers.append('provider-permissions-unhealthy')
        if missing_permissions:
            blockers.append('required-read-permission-missing')
        if not snapshot.provider_reachable:
            blockers.append('provider-unreachable')

        state = 'verified-read-only' if not blockers else 'blocked'
        return self._persist_verification(AccountVerification(
            account_id=account_id,
            state=state,
            identity_match=identity_match,
            token_healthy=token_healthy,
            permissions_healthy=permissions_healthy,
            provider_reachable=snapshot.provider_reachable,
            blockers=tuple(dict.fromkeys(blockers)),
            observed_at=snapshot.observed_at,
            external_calls_made=snapshot.external_calls_made,
        ))

    def _persist_health(self, snapshot: ProviderHealthSnapshot) -> None:
        with self._connect() as conn:
            conn.execute('''INSERT INTO meta_provider_health VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(account_id) DO UPDATE SET
                    provider_account_ref=excluded.provider_account_ref,
                    username=excluded.username,
                    token_state=excluded.token_state,
                    permission_state=excluded.permission_state,
                    granted_permissions_csv=excluded.granted_permissions_csv,
                    provider_reachable=excluded.provider_reachable,
                    observed_at=excluded.observed_at,
                    external_calls_made=excluded.external_calls_made''', (
                snapshot.account_id, snapshot.provider_account_ref, snapshot.username,
                snapshot.token_state, snapshot.permission_state,
                ','.join(snapshot.granted_permissions), int(snapshot.provider_reachable),
                snapshot.observed_at, snapshot.external_calls_made,
            ))

    def _persist_verification(self, verification: AccountVerification) -> AccountVerification:
        with self._connect() as conn:
            conn.execute('''INSERT INTO meta_account_verification VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(account_id) DO UPDATE SET
                    state=excluded.state,identity_match=excluded.identity_match,
                    token_healthy=excluded.token_healthy,permissions_healthy=excluded.permissions_healthy,
                    provider_reachable=excluded.provider_reachable,blockers_csv=excluded.blockers_csv,
                    observed_at=excluded.observed_at,external_calls_made=excluded.external_calls_made''', (
                verification.account_id, verification.state, int(verification.identity_match),
                int(verification.token_healthy), int(verification.permissions_healthy),
                int(verification.provider_reachable), ','.join(verification.blockers),
                verification.observed_at, verification.external_calls_made,
            ))
        return verification

    def get_verification(self, account_id: str) -> AccountVerification | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM meta_account_verification WHERE account_id=?', (account_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        for key in ('identity_match', 'token_healthy', 'permissions_healthy', 'provider_reachable'):
            data[key] = bool(data[key])
        data['blockers'] = tuple(filter(None, data.pop('blockers_csv').split(',')))
        return AccountVerification(**data)

    def snapshot(self) -> dict:
        with self._connect() as conn:
            verified = conn.execute("SELECT COUNT(*) FROM meta_account_verification WHERE state='verified-read-only'").fetchone()[0]
            blocked = conn.execute("SELECT COUNT(*) FROM meta_account_verification WHERE state='blocked'").fetchone()[0]
        return {
            'verified_read_only_accounts': verified,
            'blocked_accounts': blocked,
            'provider_mode': 'read-only',
            'publishing_enabled': False,
            'write_boundary_available': False,
            'stores_access_token_secrets': False,
            'external_calls_made': 0,
        }
