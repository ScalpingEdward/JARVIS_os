from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.content.auron_instagram_controlled_publish_v21_545 import ControlledInstagramPublishService, PublishDecision


class PublishReconciliationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderPublishStatus:
    provider_media_id: str
    state: str
    content_id: str
    account_id: str
    observed_at: str
    retryable: bool = False
    external_calls_made: int = 0


@dataclass(frozen=True)
class ReconciliationRecord:
    publish_id: str
    provider_media_id: str | None
    state: str
    blockers: tuple[str, ...]
    attempt: int
    next_retry_allowed: bool
    reconciled_at: str
    external_calls_made: int


class InstagramProviderResultBoundary(Protocol):
    def read_publish_status(self, provider_media_id: str) -> ProviderPublishStatus: ...


class DisabledInstagramProviderResultBoundary:
    def read_publish_status(self, provider_media_id: str) -> ProviderPublishStatus:
        raise PublishReconciliationError('Instagram provider result boundary is disabled')


class InstagramPublishReconciliationService:
    """C7 verifies provider results and controls retries without blind resubmission."""

    def __init__(self, db_path: str | Path, publish_service: ControlledInstagramPublishService,
                 result_reader: InstagramProviderResultBoundary | None = None,
                 max_retry_attempts: int = 3) -> None:
        if max_retry_attempts < 0:
            raise PublishReconciliationError('max_retry_attempts must be non-negative')
        self.db_path = str(db_path)
        self.publish_service = publish_service
        self.result_reader = result_reader or DisabledInstagramProviderResultBoundary()
        self.max_retry_attempts = max_retry_attempts
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
            conn.execute('''CREATE TABLE IF NOT EXISTS instagram_publish_reconciliation (
                publish_id TEXT PRIMARY KEY,
                provider_media_id TEXT,
                state TEXT NOT NULL,
                blockers_json TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                next_retry_allowed INTEGER NOT NULL,
                reconciled_at TEXT NOT NULL,
                external_calls_made INTEGER NOT NULL
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS instagram_publish_reconciliation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                publish_id TEXT NOT NULL,
                state TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                observed_at TEXT NOT NULL,
                details_json TEXT NOT NULL
            )''')

    def reconcile(self, plan_id: str) -> ReconciliationRecord:
        decision = self.publish_service.get_decision_by_plan(plan_id)
        if decision is None:
            raise PublishReconciliationError('publish decision not found')
        return self.reconcile_decision(decision)

    def reconcile_decision(self, decision: PublishDecision) -> ReconciliationRecord:
        current = self.get(decision.publish_id)
        attempt = 1 if current is None else current.attempt + 1
        blockers: list[str] = []
        external_calls = 0
        retry_allowed = False

        if decision.state == 'provider-write-disabled':
            state = 'blocked-provider-write-disabled'
            blockers.append('provider-write-disabled')
        elif decision.state == 'provider-error':
            state = 'retry-eligible' if attempt <= self.max_retry_attempts else 'retry-exhausted'
            retry_allowed = state == 'retry-eligible'
            blockers.append('provider-submit-error')
        elif decision.state != 'provider-submitted' or not decision.provider_media_id:
            state = 'pending-provider-submission'
            blockers.append('provider-submission-required')
        else:
            try:
                status = self.result_reader.read_publish_status(decision.provider_media_id)
                external_calls = status.external_calls_made
            except PublishReconciliationError:
                state = 'provider-result-unavailable'
                blockers.append('provider-result-boundary-disabled')
            except Exception:
                state = 'retry-eligible' if attempt <= self.max_retry_attempts else 'retry-exhausted'
                retry_allowed = state == 'retry-eligible'
                blockers.append('provider-result-read-error')
            else:
                if status.provider_media_id != decision.provider_media_id:
                    state = 'mismatched'
                    blockers.append('provider-media-id-mismatch')
                elif status.content_id != decision.content_id:
                    state = 'mismatched'
                    blockers.append('provider-content-mismatch')
                elif status.account_id != decision.account_id:
                    state = 'mismatched'
                    blockers.append('provider-account-mismatch')
                elif status.state == 'published':
                    state = 'matched-published'
                elif status.state in {'processing', 'pending'}:
                    state = 'pending-provider-result'
                elif status.retryable and attempt <= self.max_retry_attempts:
                    state = 'retry-eligible'
                    retry_allowed = True
                    blockers.append('provider-reported-retryable-failure')
                else:
                    state = 'failed-provider-result'
                    blockers.append('provider-reported-failure')

        record = ReconciliationRecord(
            publish_id=decision.publish_id,
            provider_media_id=decision.provider_media_id,
            state=state,
            blockers=tuple(dict.fromkeys(blockers)),
            attempt=attempt,
            next_retry_allowed=retry_allowed,
            reconciled_at=self._now(),
            external_calls_made=external_calls,
        )
        self._persist(record)
        return record

    def require_reconciled_published(self, publish_id: str) -> ReconciliationRecord:
        record = self.get(publish_id)
        if record is None or record.state != 'matched-published':
            raise PublishReconciliationError('publish is not provider-verified as published')
        return record

    def _persist(self, record: ReconciliationRecord) -> None:
        with self._connect() as conn:
            conn.execute('''INSERT INTO instagram_publish_reconciliation VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(publish_id) DO UPDATE SET
                provider_media_id=excluded.provider_media_id,state=excluded.state,
                blockers_json=excluded.blockers_json,attempt=excluded.attempt,
                next_retry_allowed=excluded.next_retry_allowed,
                reconciled_at=excluded.reconciled_at,external_calls_made=excluded.external_calls_made''', (
                record.publish_id, record.provider_media_id, record.state,
                json.dumps(record.blockers), record.attempt, int(record.next_retry_allowed),
                record.reconciled_at, record.external_calls_made,
            ))
            conn.execute('''INSERT INTO instagram_publish_reconciliation_events
                (publish_id,state,attempt,observed_at,details_json) VALUES (?,?,?,?,?)''', (
                record.publish_id, record.state, record.attempt, record.reconciled_at,
                json.dumps({'blockers': record.blockers, 'provider_media_id': record.provider_media_id}),
            ))

    def get(self, publish_id: str) -> ReconciliationRecord | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM instagram_publish_reconciliation WHERE publish_id=?', (publish_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['blockers'] = tuple(json.loads(data.pop('blockers_json')))
        data['next_retry_allowed'] = bool(data['next_retry_allowed'])
        return ReconciliationRecord(**data)

    def events(self, publish_id: str) -> tuple[dict, ...]:
        with self._connect() as conn:
            rows = conn.execute('''SELECT state,attempt,observed_at,details_json
                                   FROM instagram_publish_reconciliation_events
                                   WHERE publish_id=? ORDER BY id''', (publish_id,)).fetchall()
        return tuple({**dict(row), 'details': json.loads(row['details_json'])} for row in rows)
