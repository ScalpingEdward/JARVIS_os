from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class CrossVerticalSimulationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CrossVerticalSimulationStep:
    ordinal: int
    source_vertical: str
    target_vertical: str
    boundary: str
    payload_hash: str
    state: str


@dataclass(frozen=True)
class CrossVerticalSimulationRun:
    run_id: str
    scenario_id: str
    state: str
    steps: tuple[CrossVerticalSimulationStep, ...]
    run_hash: str
    created_at: str
    provider_writes_made: int = 0
    live_actions_made: int = 0


class CrossVerticalSimulationHarness:
    """E2 deterministic cross-vertical handoff simulation.

    The harness validates only governed boundary-to-boundary handoffs. It has no provider
    transport and cannot execute Trading, Content, Communications, Research, Automation
    or Documents actions.
    """

    ALLOWED_VERTICALS = frozenset({
        'trading', 'instagram-content', 'communications', 'research', 'automation', 'files-documents'
    })

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS cross_vertical_simulation_runs (
                run_id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL, run_hash TEXT NOT NULL, created_at TEXT NOT NULL,
                provider_writes_made INTEGER NOT NULL, live_actions_made INTEGER NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS cross_vertical_simulation_steps (
                run_id TEXT NOT NULL, ordinal INTEGER NOT NULL, source_vertical TEXT NOT NULL,
                target_vertical TEXT NOT NULL, boundary TEXT NOT NULL, payload_hash TEXT NOT NULL,
                state TEXT NOT NULL, PRIMARY KEY(run_id, ordinal))''')

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(payload) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def simulate(self, scenario_id: str, handoffs: tuple[dict, ...], *, at: str | None = None) -> CrossVerticalSimulationRun:
        scenario = scenario_id.strip()
        if not scenario:
            raise CrossVerticalSimulationError('scenario id is required')
        if not handoffs:
            raise CrossVerticalSimulationError('at least one handoff is required')

        existing = self.get_by_scenario(scenario)
        if existing is not None:
            return existing

        steps: list[CrossVerticalSimulationStep] = []
        canonical: list[dict] = []
        for ordinal, handoff in enumerate(handoffs, start=1):
            source = str(handoff.get('source_vertical', '')).strip()
            target = str(handoff.get('target_vertical', '')).strip()
            boundary = str(handoff.get('boundary', '')).strip()
            payload = handoff.get('payload', {})
            if source not in self.ALLOWED_VERTICALS or target not in self.ALLOWED_VERTICALS:
                raise CrossVerticalSimulationError('unknown vertical in handoff')
            if source == target:
                raise CrossVerticalSimulationError('cross-vertical handoff must change vertical')
            if not boundary or boundary.startswith('provider:'):
                raise CrossVerticalSimulationError('governed public boundary required')
            payload_hash = self._hash(payload)
            canonical.append({'ordinal': ordinal, 'source': source, 'target': target,
                              'boundary': boundary, 'payload_hash': payload_hash})
            steps.append(CrossVerticalSimulationStep(
                ordinal, source, target, boundary, payload_hash, 'simulated-not-executed'))

        run_hash = self._hash({'scenario_id': scenario, 'steps': canonical})
        run_id = 'xsim-' + run_hash[:24]
        created = at or self._now()
        run = CrossVerticalSimulationRun(run_id, scenario, 'completed-simulation', tuple(steps), run_hash, created, 0, 0)
        with self._connect() as conn:
            conn.execute('INSERT INTO cross_vertical_simulation_runs VALUES (?,?,?,?,?,?,?)',
                         (run.run_id, run.scenario_id, run.state, run.run_hash, run.created_at, 0, 0))
            for step in steps:
                conn.execute('INSERT INTO cross_vertical_simulation_steps VALUES (?,?,?,?,?,?,?)',
                             (run.run_id, step.ordinal, step.source_vertical, step.target_vertical,
                              step.boundary, step.payload_hash, step.state))
        return run

    def get_by_scenario(self, scenario_id: str) -> CrossVerticalSimulationRun | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM cross_vertical_simulation_runs WHERE scenario_id=?',(scenario_id,)).fetchone()
            if not row:
                return None
            steps = conn.execute('SELECT * FROM cross_vertical_simulation_steps WHERE run_id=? ORDER BY ordinal',(row['run_id'],)).fetchall()
        step_objs = tuple(CrossVerticalSimulationStep(r['ordinal'],r['source_vertical'],r['target_vertical'],r['boundary'],r['payload_hash'],r['state']) for r in steps)
        return CrossVerticalSimulationRun(row['run_id'],row['scenario_id'],row['state'],step_objs,row['run_hash'],row['created_at'],row['provider_writes_made'],row['live_actions_made'])
