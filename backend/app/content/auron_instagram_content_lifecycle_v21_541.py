from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.content.auron_instagram_registry_calendar_v21_540 import InstagramContentRegistryCalendar

LifecycleState = Literal['idea','draft','assets','review','approved','scheduled','publishing','result','cancelled']


class ContentLifecycleError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContentRevision:
    revision_id: str
    content_id: str
    version: int
    caption: str
    hashtags: tuple[str, ...]
    asset_uris: tuple[str, ...]
    creative_notes: str
    actor: str
    reason: str
    integrity_hash: str
    created_at: str


@dataclass(frozen=True)
class ContentLifecycleRecord:
    content_id: str
    state: LifecycleState
    current_version: int
    scheduled_for: str | None
    publish_result: str | None
    updated_at: str
    external_calls_made: int = 0


_ALLOWED_TRANSITIONS: dict[LifecycleState, tuple[LifecycleState, ...]] = {
    'idea': ('draft', 'cancelled'),
    'draft': ('assets', 'review', 'cancelled'),
    'assets': ('review', 'draft', 'cancelled'),
    'review': ('approved', 'draft', 'cancelled'),
    'approved': ('scheduled', 'draft', 'cancelled'),
    'scheduled': ('publishing', 'draft', 'cancelled'),
    'publishing': ('result',),
    'result': (),
    'cancelled': (),
}


class InstagramContentLifecycle:
    """C2 lifecycle and immutable revision history over the C1 calendar.

    Metadata revisions are append-only. Lifecycle state is controlled separately.
    No Meta/Instagram provider call exists in C2; `publishing` is only an internal
    workflow state to be consumed by later gated provider modules.
    """

    def __init__(self, db_path: str | Path, registry: InstagramContentRegistryCalendar) -> None:
        self.db_path = str(db_path)
        self.registry = registry
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
            conn.execute('''CREATE TABLE IF NOT EXISTS content_lifecycle (
                content_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                current_version INTEGER NOT NULL,
                scheduled_for TEXT,
                publish_result TEXT,
                updated_at TEXT NOT NULL
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS content_revisions (
                revision_id TEXT PRIMARY KEY,
                content_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                caption TEXT NOT NULL,
                hashtags_json TEXT NOT NULL,
                asset_uris_json TEXT NOT NULL,
                creative_notes TEXT NOT NULL,
                actor TEXT NOT NULL,
                reason TEXT NOT NULL,
                integrity_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(content_id, version)
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_content_revisions_content ON content_revisions(content_id, version)')

    @staticmethod
    def _normalize_hashtags(values: tuple[str, ...]) -> tuple[str, ...]:
        result: list[str] = []
        for value in values:
            cleaned = value.strip().lstrip('#')
            if cleaned and cleaned.lower() not in {x.lower() for x in result}:
                result.append(cleaned)
        return tuple(result)

    @staticmethod
    def _hash_payload(content_id: str, version: int, caption: str, hashtags: tuple[str, ...],
                      asset_uris: tuple[str, ...], creative_notes: str, actor: str, reason: str) -> str:
        payload = {
            'content_id': content_id,
            'version': version,
            'caption': caption,
            'hashtags': hashtags,
            'asset_uris': asset_uris,
            'creative_notes': creative_notes,
            'actor': actor,
            'reason': reason,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def initialize(self, content_id: str, *, caption: str = '', hashtags: tuple[str, ...] = (),
                   asset_uris: tuple[str, ...] = (), creative_notes: str = '',
                   actor: str = 'operator', reason: str = 'initial') -> ContentLifecycleRecord:
        entry = self.registry.get_calendar_entry(content_id)
        if entry is None:
            raise ContentLifecycleError('C1 calendar entry must exist before lifecycle initialization')
        existing = self.get(content_id)
        if existing is not None:
            return existing
        now = self._now()
        with self._connect() as conn:
            conn.execute('INSERT INTO content_lifecycle VALUES (?,?,?,?,?,?)',
                         (content_id, 'idea', 0, entry.scheduled_for, None, now))
        self.add_revision(content_id, caption=caption, hashtags=hashtags, asset_uris=asset_uris,
                          creative_notes=creative_notes, actor=actor, reason=reason)
        result = self.get(content_id)
        if result is None:
            raise ContentLifecycleError('lifecycle initialization failed')
        return result

    def add_revision(self, content_id: str, *, caption: str, hashtags: tuple[str, ...] = (),
                     asset_uris: tuple[str, ...] = (), creative_notes: str = '',
                     actor: str, reason: str) -> ContentRevision:
        lifecycle = self.get(content_id)
        if lifecycle is None:
            raise ContentLifecycleError('lifecycle must be initialized before revision')
        if lifecycle.state in {'publishing', 'result', 'cancelled'}:
            raise ContentLifecycleError('content metadata is locked in terminal/publishing states')
        if not actor.strip() or not reason.strip():
            raise ContentLifecycleError('actor and reason are required for immutable revision history')
        version = lifecycle.current_version + 1
        normalized_hashtags = self._normalize_hashtags(tuple(hashtags))
        normalized_assets = tuple(uri.strip() for uri in asset_uris if uri.strip())
        integrity_hash = self._hash_payload(content_id, version, caption, normalized_hashtags,
                                            normalized_assets, creative_notes, actor, reason)
        created_at = self._now()
        revision_id = f'{content_id}:v{version}'
        with self._connect() as conn:
            conn.execute('''INSERT INTO content_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (
                revision_id, content_id, version, caption, json.dumps(normalized_hashtags),
                json.dumps(normalized_assets), creative_notes, actor.strip(), reason.strip(),
                integrity_hash, created_at,
            ))
            conn.execute('UPDATE content_lifecycle SET current_version=?, updated_at=? WHERE content_id=?',
                         (version, created_at, content_id))
        return self.get_revision(content_id, version)

    def transition(self, content_id: str, target: LifecycleState, *, scheduled_for: str | None = None,
                   publish_result: str | None = None) -> ContentLifecycleRecord:
        current = self.get(content_id)
        if current is None:
            raise ContentLifecycleError('lifecycle not initialized')
        if target not in _ALLOWED_TRANSITIONS[current.state]:
            raise ContentLifecycleError(f'invalid lifecycle transition: {current.state} -> {target}')
        if target == 'scheduled' and not scheduled_for:
            raise ContentLifecycleError('scheduled transition requires scheduled_for')
        if target == 'result' and not publish_result:
            raise ContentLifecycleError('result transition requires publish_result')
        schedule = scheduled_for if target == 'scheduled' else current.scheduled_for
        result = publish_result if target == 'result' else current.publish_result
        now = self._now()
        with self._connect() as conn:
            conn.execute('UPDATE content_lifecycle SET state=?, scheduled_for=?, publish_result=?, updated_at=? WHERE content_id=?',
                         (target, schedule, result, now, content_id))
            calendar_state = target if target in {'idea','draft','review','approved','scheduled','cancelled'} else None
            if target == 'result' and publish_result == 'published':
                calendar_state = 'published'
            if calendar_state is not None:
                conn.execute('UPDATE content_calendar SET state=?, scheduled_for=?, updated_at=? WHERE content_id=?',
                             (calendar_state, schedule, now, content_id))
        result_record = self.get(content_id)
        if result_record is None:
            raise ContentLifecycleError('transition persistence failed')
        return result_record

    def get(self, content_id: str) -> ContentLifecycleRecord | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM content_lifecycle WHERE content_id=?', (content_id,)).fetchone()
        return ContentLifecycleRecord(**dict(row), external_calls_made=0) if row else None

    def get_revision(self, content_id: str, version: int) -> ContentRevision | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM content_revisions WHERE content_id=? AND version=?',
                               (content_id, version)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['hashtags'] = tuple(json.loads(data.pop('hashtags_json')))
        data['asset_uris'] = tuple(json.loads(data.pop('asset_uris_json')))
        return ContentRevision(**data)

    def revision_history(self, content_id: str) -> tuple[ContentRevision, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT version FROM content_revisions WHERE content_id=? ORDER BY version ASC',
                                (content_id,)).fetchall()
        return tuple(self.get_revision(content_id, row['version']) for row in rows)

    def snapshot(self, content_id: str) -> dict:
        lifecycle = self.get(content_id)
        if lifecycle is None:
            raise ContentLifecycleError('lifecycle not initialized')
        latest = self.get_revision(content_id, lifecycle.current_version)
        return {
            'lifecycle': lifecycle,
            'latest_revision': latest,
            'revision_count': len(self.revision_history(content_id)),
            'provider_connected': False,
            'publishing_enabled': False,
            'external_calls_made': 0,
        }
