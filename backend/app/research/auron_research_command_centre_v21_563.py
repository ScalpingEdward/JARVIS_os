from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.research.auron_research_controlled_watch_v21_561 import ControlledResearchWatchService
from app.research.auron_research_registry_evidence_v21_557 import ResearchRegistryEvidenceStore
from app.research.auron_research_report_simulation_v21_560 import ResearchReportSimulationService
from app.research.auron_research_watch_reconciliation_v21_562 import ResearchWatchReconciliationService


class ResearchCommandCentreError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchCommandJournalEntry:
    command_id: int
    actor: str
    command_text: str
    state: str
    created_at: str


class ResearchCommandCentre:
    """D16 operational read model and safe controls for Research.

    The Command Centre exposes research provenance/freshness/watch state and governed
    kill controls. Text commands are persisted as operator intent only and never execute
    research, Trading, Content or Communications actions directly.
    """

    def __init__(self, db_path: str | Path, registry: ResearchRegistryEvidenceStore,
                 reports: ResearchReportSimulationService,
                 watches: ControlledResearchWatchService,
                 reconciliation: ResearchWatchReconciliationService) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.reports = reports
        self.watches = watches
        self.reconciliation = reconciliation
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
            conn.execute('''CREATE TABLE IF NOT EXISTS research_command_journal (
                command_id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL, command_text TEXT NOT NULL,
                state TEXT NOT NULL, created_at TEXT NOT NULL)''')

    @staticmethod
    def _read_rows(db_path: str, sql: str) -> tuple[dict, ...]:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            return tuple(dict(row) for row in conn.execute(sql).fetchall())
        except sqlite3.OperationalError:
            return ()
        finally:
            conn.close()

    def snapshot(self, *, now: str | None = None) -> dict:
        observed_at = now or self._now()
        queries = self._read_rows(
            self.registry.db_path,
            'SELECT query_id,query_text,provider_id,requested_at,state FROM research_queries ORDER BY requested_at DESC',
        )
        sources = self._read_rows(
            self.registry.db_path,
            '''SELECT source_id,provider_id,canonical_url,title,publisher,published_at,
                      retrieved_at,content_hash,attribution FROM research_sources ORDER BY retrieved_at DESC''',
        )
        results = self._read_rows(
            self.registry.db_path,
            '''SELECT result_id,query_id,source_id,rank,snippet,evidence_hash,observed_at
               FROM research_results ORDER BY observed_at DESC,rank''',
        )
        reports = self._read_rows(
            self.reports.db_path,
            '''SELECT report_id,query_id,minimum_confidence,state,evidence_count,report_hash,
                      created_at,downstream_execution_enabled,external_calls_made
               FROM research_report_simulations ORDER BY created_at DESC''',
        )
        watch_policies = self._read_rows(
            self.watches.db_path,
            '''SELECT watch_id,provider_id,query_text,interval_seconds,result_limit,
                      minimum_confidence,enabled,operator_enabled,kill_switch,created_at,updated_at
               FROM research_watch_policies ORDER BY updated_at DESC''',
        )
        watch_runs = self._read_rows(
            self.watches.db_path,
            '''SELECT run_id,watch_id,scheduled_for,started_at,state,query_id,report_id,
                      external_calls_made,downstream_actions_made
               FROM research_watch_runs ORDER BY scheduled_for DESC''',
        )
        reconciliations = self._read_rows(
            self.reconciliation.db_path,
            '''SELECT reconciliation_id,run_id,watch_id,state,freshness_state,source_count,
                      fresh_sources,aging_sources,stale_sources,retry_attempt,retry_due_at,
                      terminal,reconciled_at,downstream_actions_made
               FROM research_watch_reconciliations ORDER BY reconciled_at DESC''',
        )

        freshness: list[dict] = []
        for source in sources:
            try:
                state = self.registry.evidence_state(source['source_id'], now=observed_at)
                freshness.append(asdict(state))
            except Exception:
                freshness.append({
                    'source_id': source['source_id'], 'freshness_state': 'unknown',
                    'age_seconds': -1, 'observed_at': observed_at,
                })

        alerts: list[dict] = []
        stale_count = sum(1 for item in freshness if item['freshness_state'] == 'stale')
        aging_count = sum(1 for item in freshness if item['freshness_state'] == 'aging')
        if stale_count:
            alerts.append({'kind': 'freshness', 'severity': 'warning', 'state': 'stale', 'count': stale_count})
        if aging_count:
            alerts.append({'kind': 'freshness', 'severity': 'info', 'state': 'aging', 'count': aging_count})
        for run in watch_runs:
            if run['state'].startswith('blocked:') or run['state'].startswith('failed:'):
                alerts.append({'kind': 'watch-run', 'severity': 'warning', 'run_id': run['run_id'], 'state': run['state']})
        for item in reconciliations:
            if item['state'] in {'retry-scheduled', 'retry-exhausted', 'freshness-failed-stale-evidence', 'unknown-run-state'}:
                alerts.append({'kind': 'reconciliation', 'severity': 'warning', 'run_id': item['run_id'], 'state': item['state']})

        return {
            'workspace': 'research',
            'command_field_enabled': True,
            'queries': queries,
            'sources': sources,
            'results': results,
            'source_freshness': tuple(freshness),
            'reports': reports,
            'watch_policies': watch_policies,
            'watch_runs': watch_runs,
            'reconciliations': reconciliations,
            'alerts': tuple(alerts),
            'unattended_actions_enabled_by_default': False,
            'downstream_execution_enabled': False,
        }

    def set_watch_kill_switch(self, watch_id: str, *, active: bool,
                              now: str | None = None) -> dict:
        current = self.watches.get_policy(watch_id)
        if current is None:
            raise ResearchCommandCentreError('research watch not found')
        updated = self.watches.configure(
            provider_id=current.provider_id,
            query_text=current.query_text,
            interval_seconds=current.interval_seconds,
            result_limit=current.result_limit,
            minimum_confidence=current.minimum_confidence,
            enabled=current.enabled,
            operator_enabled=current.operator_enabled,
            kill_switch=active,
            now=now,
        )
        return asdict(updated)

    def record_command(self, command_text: str, *, actor: str) -> ResearchCommandJournalEntry:
        command, operator = command_text.strip(), actor.strip()
        if not command or not operator:
            raise ResearchCommandCentreError('command text and actor are required')
        with self._connect() as conn:
            cur = conn.execute(
                'INSERT INTO research_command_journal(actor,command_text,state,created_at) VALUES (?,?,?,?)',
                (operator, command, 'recorded-not-executed', self._now()),
            )
            command_id = int(cur.lastrowid)
        return self.get_command(command_id)

    def get_command(self, command_id: int) -> ResearchCommandJournalEntry:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM research_command_journal WHERE command_id=?', (command_id,)).fetchone()
        if row is None:
            raise ResearchCommandCentreError('research command journal entry not found')
        return ResearchCommandJournalEntry(**dict(row))

    def list_commands(self) -> tuple[ResearchCommandJournalEntry, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM research_command_journal ORDER BY command_id DESC').fetchall()
        return tuple(ResearchCommandJournalEntry(**dict(row)) for row in rows)
