from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

AccountStatus = Literal['active', 'paused', 'disabled']
CalendarState = Literal['idea', 'draft', 'review', 'approved', 'scheduled', 'published', 'cancelled']
ContentType = Literal['reel', 'post', 'carousel', 'story']


class ContentRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class Brand:
    brand_id: str
    name: str
    timezone: str
    default_language: str
    status: AccountStatus = 'active'


@dataclass(frozen=True)
class InstagramAccount:
    account_id: str
    brand_id: str
    handle: str
    provider_account_ref: str | None
    status: AccountStatus
    publishing_enabled: bool = False


@dataclass(frozen=True)
class CalendarEntry:
    content_id: str
    brand_id: str
    account_id: str
    content_type: ContentType
    title: str
    state: CalendarState
    scheduled_for: str | None
    created_at: str
    updated_at: str


class InstagramContentRegistryCalendar:
    """C1 persistent brand/account registry plus content calendar.

    C1 does not connect to Meta/Instagram and cannot publish content. Publishing is
    explicitly disabled on account creation and remains a later gated capability.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS content_brands (
                    brand_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    default_language TEXT NOT NULL,
                    status TEXT NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS instagram_accounts (
                    account_id TEXT PRIMARY KEY,
                    brand_id TEXT NOT NULL,
                    handle TEXT NOT NULL UNIQUE,
                    provider_account_ref TEXT,
                    status TEXT NOT NULL,
                    publishing_enabled INTEGER NOT NULL,
                    FOREIGN KEY(brand_id) REFERENCES content_brands(brand_id)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS content_calendar (
                    content_id TEXT PRIMARY KEY,
                    brand_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    state TEXT NOT NULL,
                    scheduled_for TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(brand_id) REFERENCES content_brands(brand_id),
                    FOREIGN KEY(account_id) REFERENCES instagram_accounts(account_id)
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_content_calendar_schedule ON content_calendar(scheduled_for)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_content_calendar_account ON content_calendar(account_id)')

    def upsert_brand(self, brand: Brand) -> Brand:
        if not brand.brand_id.strip() or not brand.name.strip() or not brand.timezone.strip() or not brand.default_language.strip():
            raise ContentRegistryError('brand id, name, timezone and language are required')
        with self._connect() as conn:
            conn.execute('''
                INSERT INTO content_brands VALUES (?,?,?,?,?)
                ON CONFLICT(brand_id) DO UPDATE SET
                    name=excluded.name,timezone=excluded.timezone,
                    default_language=excluded.default_language,status=excluded.status
            ''', (brand.brand_id, brand.name, brand.timezone, brand.default_language, brand.status))
        return self.get_brand(brand.brand_id)

    def get_brand(self, brand_id: str) -> Brand | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM content_brands WHERE brand_id=?', (brand_id,)).fetchone()
        return Brand(**dict(row)) if row else None

    def list_brands(self) -> list[Brand]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM content_brands ORDER BY name').fetchall()
        return [Brand(**dict(row)) for row in rows]

    def register_account(self, account: InstagramAccount) -> InstagramAccount:
        if self.get_brand(account.brand_id) is None:
            raise ContentRegistryError('brand must exist before Instagram account registration')
        if account.publishing_enabled:
            raise ContentRegistryError('C1 accounts must start with publishing disabled')
        handle = account.handle.strip().lstrip('@')
        if not handle:
            raise ContentRegistryError('Instagram handle is required')
        stored = InstagramAccount(account.account_id, account.brand_id, handle, account.provider_account_ref, account.status, False)
        try:
            with self._connect() as conn:
                conn.execute('INSERT INTO instagram_accounts VALUES (?,?,?,?,?,?)', (
                    stored.account_id, stored.brand_id, stored.handle, stored.provider_account_ref,
                    stored.status, int(stored.publishing_enabled),
                ))
        except sqlite3.IntegrityError as exc:
            raise ContentRegistryError('duplicate Instagram account id/handle or invalid brand') from exc
        return self.get_account(stored.account_id)

    def get_account(self, account_id: str) -> InstagramAccount | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM instagram_accounts WHERE account_id=?', (account_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['publishing_enabled'] = bool(data['publishing_enabled'])
        return InstagramAccount(**data)

    def list_accounts(self, brand_id: str | None = None) -> list[InstagramAccount]:
        with self._connect() as conn:
            if brand_id is None:
                rows = conn.execute('SELECT * FROM instagram_accounts ORDER BY brand_id,handle').fetchall()
            else:
                rows = conn.execute('SELECT * FROM instagram_accounts WHERE brand_id=? ORDER BY handle', (brand_id,)).fetchall()
        result = []
        for row in rows:
            data = dict(row); data['publishing_enabled'] = bool(data['publishing_enabled'])
            result.append(InstagramAccount(**data))
        return result

    def add_calendar_entry(self, *, content_id: str, brand_id: str, account_id: str,
                           content_type: ContentType, title: str,
                           scheduled_for: str | None = None,
                           state: CalendarState = 'idea') -> CalendarEntry:
        brand = self.get_brand(brand_id)
        account = self.get_account(account_id)
        if brand is None or account is None:
            raise ContentRegistryError('brand and account must exist before calendar entry creation')
        if account.brand_id != brand_id:
            raise ContentRegistryError('Instagram account does not belong to brand')
        if not content_id.strip() or not title.strip():
            raise ContentRegistryError('content id and title are required')
        if state == 'scheduled' and not scheduled_for:
            raise ContentRegistryError('scheduled entries require scheduled_for')
        now = self._now()
        try:
            with self._connect() as conn:
                conn.execute('INSERT INTO content_calendar VALUES (?,?,?,?,?,?,?,?,?)', (
                    content_id, brand_id, account_id, content_type, title.strip(), state,
                    scheduled_for, now, now,
                ))
        except sqlite3.IntegrityError as exc:
            raise ContentRegistryError('duplicate content id or invalid calendar references') from exc
        result = self.get_calendar_entry(content_id)
        if result is None:
            raise ContentRegistryError('calendar entry persistence failed')
        return result

    def get_calendar_entry(self, content_id: str) -> CalendarEntry | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM content_calendar WHERE content_id=?', (content_id,)).fetchone()
        return CalendarEntry(**dict(row)) if row else None

    def list_calendar(self, *, account_id: str | None = None, state: CalendarState | None = None) -> list[CalendarEntry]:
        clauses: list[str] = []
        params: list[str] = []
        if account_id is not None:
            clauses.append('account_id=?'); params.append(account_id)
        if state is not None:
            clauses.append('state=?'); params.append(state)
        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM content_calendar' + where + ' ORDER BY COALESCE(scheduled_for, created_at), content_id',
                tuple(params),
            ).fetchall()
        return [CalendarEntry(**dict(row)) for row in rows]

    def snapshot(self) -> dict:
        return {
            'brands': len(self.list_brands()),
            'instagram_accounts': len(self.list_accounts()),
            'calendar_entries': len(self.list_calendar()),
            'provider_connected': False,
            'publishing_enabled': False,
            'external_calls_made': 0,
        }
