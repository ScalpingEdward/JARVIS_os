from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.research.auron_research_read_search_fetch_v21_558 import (
    ResearchReadSearchFetchIntegration,
    ResearchReadSearchFetchProvider,
)
from app.research.auron_research_report_simulation_v21_560 import ResearchReportSimulationService


class ResearchWatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchWatchPolicy:
    watch_id: str
    provider_id: str
    query_text: str
    interval_seconds: int
    result_limit: int
    minimum_confidence: str
    enabled: bool
    operator_enabled: bool
    kill_switch: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ResearchWatchRun:
    run_id: str
    watch_id: str
    scheduled_for: str
    started_at: str
    state: str
    query_id: str | None
    report_id: str | None
    external_calls_made: int
    downstream_actions_made: int = 0


class ControlledResearchWatchService:
    """D14 controlled recurring research execution boundary.

    Watches are persisted but fail closed by default. A run requires enabled scope,
    explicit operator enablement and a clear kill switch. The watch may perform the
    governed D11 read/search/fetch flow and D13 local report simulation only. It cannot
    trigger Trading, Content or Communications execution.
    """

    MIN_INTERVAL_SECONDS = 300
    MAX_INTERVAL_SECONDS = 30 * 24 * 3600

    def __init__(self, db_path: str | Path,
                 integration: ResearchReadSearchFetchIntegration,
                 reports: ResearchReportSimulationService) -> None:
        self.db_path = str(db_path)
        self.integration = integration
        self.reports = reports
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
            raise ResearchWatchError('watch timestamps must be timezone-aware')
        return dt.astimezone(timezone.utc)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS research_watch_policies (
                    watch_id TEXT PRIMARY KEY, provider_id TEXT NOT NULL,
                    query_text TEXT NOT NULL, interval_seconds INTEGER NOT NULL,
                    result_limit INTEGER NOT NULL, minimum_confidence TEXT NOT NULL,
                    enabled INTEGER NOT NULL, operator_enabled INTEGER NOT NULL,
                    kill_switch INTEGER NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research_watch_runs (
                    run_id TEXT PRIMARY KEY, watch_id TEXT NOT NULL,
                    scheduled_for TEXT NOT NULL, started_at TEXT NOT NULL,
                    state TEXT NOT NULL, query_id TEXT, report_id TEXT,
                    external_calls_made INTEGER NOT NULL,
                    downstream_actions_made INTEGER NOT NULL,
                    UNIQUE(watch_id, scheduled_for));
            ''')

    @staticmethod
    def _watch_id(provider_id: str, query_text: str) -> str:
        raw = f'{provider_id.strip()}\x1f{query_text.strip()}'.encode()
        return 'watch-' + hashlib.sha256(raw).hexdigest()[:24]

    @staticmethod
    def _run_id(watch_id: str, scheduled_for: str) -> str:
        return 'watchrun-' + hashlib.sha256(f'{watch_id}\x1f{scheduled_for}'.encode()).hexdigest()[:24]

    def configure(self, *, provider_id: str, query_text: str,
                  interval_seconds: int, result_limit: int = 10,
                  minimum_confidence: str = 'medium', enabled: bool = False,
                  operator_enabled: bool = False, kill_switch: bool = True,
                  now: str | None = None) -> ResearchWatchPolicy:
        provider = provider_id.strip()
        query = query_text.strip()
        if not provider or not query:
            raise ResearchWatchError('provider and query are required')
        if not self.MIN_INTERVAL_SECONDS <= interval_seconds <= self.MAX_INTERVAL_SECONDS:
            raise ResearchWatchError('watch interval is outside allowed bounds')
        if not 1 <= result_limit <= 100:
            raise ResearchWatchError('result_limit must be between 1 and 100')
        if minimum_confidence not in {'low', 'medium', 'high'}:
            raise ResearchWatchError('minimum_confidence must be low, medium or high')
        at = now or self._now()
        watch_id = self._watch_id(provider, query)
        previous = self.get_policy(watch_id)
        created = previous.created_at if previous else at
        with self._connect() as conn:
            conn.execute('''INSERT INTO research_watch_policies VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(watch_id) DO UPDATE SET provider_id=excluded.provider_id,
                query_text=excluded.query_text,interval_seconds=excluded.interval_seconds,
                result_limit=excluded.result_limit,minimum_confidence=excluded.minimum_confidence,
                enabled=excluded.enabled,operator_enabled=excluded.operator_enabled,
                kill_switch=excluded.kill_switch,updated_at=excluded.updated_at''', (
                watch_id, provider, query, interval_seconds, result_limit, minimum_confidence,
                int(enabled), int(operator_enabled), int(kill_switch), created, at,
            ))
        policy = self.get_policy(watch_id)
        if policy is None:
            raise ResearchWatchError('watch policy persistence failed')
        return policy

    def get_policy(self, watch_id: str) -> ResearchWatchPolicy | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM research_watch_policies WHERE watch_id=?', (watch_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        for field in ('enabled', 'operator_enabled', 'kill_switch'):
            data[field] = bool(data[field])
        return ResearchWatchPolicy(**data)

    def next_due_at(self, watch_id: str) -> str:
        policy = self.get_policy(watch_id)
        if policy is None:
            raise ResearchWatchError('watch policy not found')
        with self._connect() as conn:
            row = conn.execute('''SELECT scheduled_for FROM research_watch_runs
                                  WHERE watch_id=? ORDER BY scheduled_for DESC LIMIT 1''', (watch_id,)).fetchone()
        base = self._parse(row['scheduled_for']) if row else self._parse(policy.created_at)
        return (base + timedelta(seconds=policy.interval_seconds)).isoformat()

    def run_if_due(self, watch_id: str, provider: ResearchReadSearchFetchProvider,
                   *, at: str | None = None) -> ResearchWatchRun | None:
        policy = self.get_policy(watch_id)
        if policy is None:
            raise ResearchWatchError('watch policy not found')
        now = self._parse(at or self._now())
        due = self._parse(self.next_due_at(watch_id))
        if now < due:
            return None
        return self.run(watch_id, provider, scheduled_for=due.isoformat(), started_at=now.isoformat())

    def run(self, watch_id: str, provider: ResearchReadSearchFetchProvider, *,
            scheduled_for: str, started_at: str | None = None) -> ResearchWatchRun:
        policy = self.get_policy(watch_id)
        if policy is None:
            raise ResearchWatchError('watch policy not found')
        existing = self.get_run(self._run_id(watch_id, scheduled_for))
        if existing is not None:
            return existing

        blockers: list[str] = []
        descriptor = provider.descriptor()
        if descriptor.provider_id != policy.provider_id:
            blockers.append('provider-identity-mismatch')
        if not policy.enabled:
            blockers.append('watch-disabled')
        if not policy.operator_enabled:
            blockers.append('operator-enablement-required')
        if policy.kill_switch:
            blockers.append('watch-kill-switch-active')
        if blockers:
            return self._persist_run(ResearchWatchRun(
                self._run_id(watch_id, scheduled_for), watch_id, scheduled_for,
                started_at or self._now(), 'blocked:' + ','.join(blockers), None, None, 0, 0,
            ))

        summary = self.integration.run_query(
            provider, policy.query_text, limit=policy.result_limit, requested_at=scheduled_for,
        )
        if not summary.results:
            return self._persist_run(ResearchWatchRun(
                self._run_id(watch_id, scheduled_for), watch_id, scheduled_for,
                started_at or self._now(), 'completed-no-results', summary.query.query_id,
                None, summary.external_calls_made, 0,
            ))
        try:
            report = self.reports.assemble(
                summary.query.query_id, minimum_confidence=policy.minimum_confidence,
                now=started_at or self._now(),
            )
            report_id = report.report_id
            state = 'completed-report-simulated'
        except Exception:
            report_id = None
            state = 'completed-no-admissible-report'

        return self._persist_run(ResearchWatchRun(
            self._run_id(watch_id, scheduled_for), watch_id, scheduled_for,
            started_at or self._now(), state, summary.query.query_id, report_id,
            summary.external_calls_made, 0,
        ))

    def _persist_run(self, run: ResearchWatchRun) -> ResearchWatchRun:
        with self._connect() as conn:
            conn.execute('INSERT OR IGNORE INTO research_watch_runs VALUES (?,?,?,?,?,?,?,?,?)', tuple(run.__dict__.values()))
        return self.get_run(run.run_id) or run

    def get_run(self, run_id: str) -> ResearchWatchRun | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM research_watch_runs WHERE run_id=?', (run_id,)).fetchone()
        return ResearchWatchRun(**dict(row)) if row else None

    def list_runs(self, watch_id: str) -> tuple[ResearchWatchRun, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM research_watch_runs WHERE watch_id=? ORDER BY scheduled_for', (watch_id,)).fetchall()
        return tuple(ResearchWatchRun(**dict(row)) for row in rows)
