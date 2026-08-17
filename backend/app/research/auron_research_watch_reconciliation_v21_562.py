from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.research.auron_research_controlled_watch_v21_561 import (
    ControlledResearchWatchService,
    ResearchReadSearchFetchProvider,
    ResearchWatchRun,
)


class ResearchWatchReconciliationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchWatchRetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: int = 300
    max_delay_seconds: int = 3600

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 5:
            raise ValueError('max_attempts must be between 1 and 5')
        if not 60 <= self.base_delay_seconds <= self.max_delay_seconds <= 86400:
            raise ValueError('retry delays are outside allowed bounds')


@dataclass(frozen=True)
class ResearchWatchReconciliation:
    reconciliation_id: str
    run_id: str
    watch_id: str
    state: str
    freshness_state: str
    source_count: int
    fresh_sources: int
    aging_sources: int
    stale_sources: int
    retry_attempt: int
    retry_due_at: str | None
    terminal: bool
    reconciled_at: str
    downstream_actions_made: int = 0


class ResearchWatchReconciliationService:
    """D15 reconciliation/freshness/retry boundary for D14 watch runs.

    Reconciliation never performs downstream actions. Retry is bounded and only re-enters
    the governed D14 research watch boundary; policy enablement, provider identity and
    kill-switch checks therefore remain authoritative on every retry.
    """

    RETRYABLE_PREFIXES = ('failed:',)

    def __init__(self, db_path: str | Path, watches: ControlledResearchWatchService,
                 retry_policy: ResearchWatchRetryPolicy | None = None) -> None:
        self.db_path = str(db_path)
        self.watches = watches
        self.retry_policy = retry_policy or ResearchWatchRetryPolicy()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse(value: str) -> datetime:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            raise ResearchWatchReconciliationError('timestamps must be timezone-aware')
        return dt.astimezone(timezone.utc)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS research_watch_reconciliations (
                reconciliation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE,
                watch_id TEXT NOT NULL, state TEXT NOT NULL, freshness_state TEXT NOT NULL,
                source_count INTEGER NOT NULL, fresh_sources INTEGER NOT NULL,
                aging_sources INTEGER NOT NULL, stale_sources INTEGER NOT NULL,
                retry_attempt INTEGER NOT NULL, retry_due_at TEXT, terminal INTEGER NOT NULL,
                reconciled_at TEXT NOT NULL, downstream_actions_made INTEGER NOT NULL)''')

    @staticmethod
    def _reconciliation_id(run_id: str) -> str:
        return 'reconcile-' + hashlib.sha256(run_id.encode()).hexdigest()[:24]

    def _retry_attempt(self, watch_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute('''SELECT COALESCE(MAX(retry_attempt),0) AS attempt
                                  FROM research_watch_reconciliations WHERE watch_id=?''', (watch_id,)).fetchone()
        return int(row['attempt'])

    def reconcile(self, run_id: str, *, at: str | None = None) -> ResearchWatchReconciliation:
        existing = self.get(run_id)
        if existing is not None:
            return existing
        run = self.watches.get_run(run_id)
        if run is None:
            raise ResearchWatchReconciliationError('watch run not found')
        now = at or self._now()
        self._parse(now)

        counts = {'fresh': 0, 'aging': 0, 'stale': 0}
        source_count = 0
        if run.query_id:
            results = self.watches.integration.registry.list_results(run.query_id)
            source_ids = tuple(dict.fromkeys(result.source_id for result in results))
            source_count = len(source_ids)
            for source_id in source_ids:
                freshness = self.watches.integration.registry.evidence_state(source_id, now=now).freshness_state
                counts[freshness] = counts.get(freshness, 0) + 1

        if counts['stale']:
            state = 'freshness-failed-stale-evidence'
            terminal = True
            retry_attempt = self._retry_attempt(run.watch_id)
            retry_due = None
        elif run.state.startswith('blocked:'):
            state = 'policy-blocked'
            terminal = True
            retry_attempt = self._retry_attempt(run.watch_id)
            retry_due = None
        elif run.state.startswith(self.RETRYABLE_PREFIXES):
            retry_attempt = self._retry_attempt(run.watch_id) + 1
            if retry_attempt >= self.retry_policy.max_attempts:
                state = 'retry-exhausted'
                terminal = True
                retry_due = None
            else:
                delay = min(self.retry_policy.base_delay_seconds * (2 ** (retry_attempt - 1)), self.retry_policy.max_delay_seconds)
                retry_due = (self._parse(now) + timedelta(seconds=delay)).isoformat()
                state = 'retry-scheduled'
                terminal = False
        elif run.state in {'completed-report-simulated', 'completed-no-results', 'completed-no-admissible-report'}:
            retry_attempt = self._retry_attempt(run.watch_id)
            retry_due = None
            state = 'reconciled'
            terminal = True
        else:
            retry_attempt = self._retry_attempt(run.watch_id)
            retry_due = None
            state = 'unknown-run-state'
            terminal = True

        if source_count == 0:
            freshness_state = 'no-evidence'
        elif counts['stale']:
            freshness_state = 'stale'
        elif counts['aging']:
            freshness_state = 'aging'
        else:
            freshness_state = 'fresh'

        record = ResearchWatchReconciliation(
            reconciliation_id=self._reconciliation_id(run_id), run_id=run_id,
            watch_id=run.watch_id, state=state, freshness_state=freshness_state,
            source_count=source_count, fresh_sources=counts['fresh'], aging_sources=counts['aging'],
            stale_sources=counts['stale'], retry_attempt=retry_attempt, retry_due_at=retry_due,
            terminal=terminal, reconciled_at=now, downstream_actions_made=0,
        )
        return self._persist(record)

    def retry_if_due(self, run_id: str, provider: ResearchReadSearchFetchProvider,
                     *, at: str | None = None) -> ResearchWatchRun | None:
        reconciliation = self.get(run_id) or self.reconcile(run_id, at=at)
        if reconciliation.terminal or not reconciliation.retry_due_at:
            return None
        now = self._parse(at or self._now())
        due = self._parse(reconciliation.retry_due_at)
        if now < due:
            return None
        retry_slot = f'{self.watches.get_run(run_id).scheduled_for}#retry-{reconciliation.retry_attempt}'
        return self.watches.run(
            reconciliation.watch_id, provider, scheduled_for=retry_slot, started_at=now.isoformat(),
        )

    def _persist(self, record: ResearchWatchReconciliation) -> ResearchWatchReconciliation:
        with self._connect() as conn:
            conn.execute('INSERT OR IGNORE INTO research_watch_reconciliations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                record.reconciliation_id, record.run_id, record.watch_id, record.state,
                record.freshness_state, record.source_count, record.fresh_sources,
                record.aging_sources, record.stale_sources, record.retry_attempt,
                record.retry_due_at, int(record.terminal), record.reconciled_at,
                record.downstream_actions_made,
            ))
        return self.get(record.run_id) or record

    def get(self, run_id: str) -> ResearchWatchReconciliation | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM research_watch_reconciliations WHERE run_id=?', (run_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['terminal'] = bool(data['terminal'])
        return ResearchWatchReconciliation(**data)

    def list_for_watch(self, watch_id: str) -> tuple[ResearchWatchReconciliation, ...]:
        with self._connect() as conn:
            rows = conn.execute('''SELECT run_id FROM research_watch_reconciliations
                                   WHERE watch_id=? ORDER BY reconciled_at,run_id''', (watch_id,)).fetchall()
        return tuple(self.get(row['run_id']) for row in rows)
