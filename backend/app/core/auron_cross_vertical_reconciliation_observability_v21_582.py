from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.auron_cross_vertical_simulation_harness_v21_581 import CrossVerticalSimulationHarness


class CrossVerticalReconciliationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CrossVerticalStepObservation:
    ordinal: int
    correlation_id: str
    source_vertical: str
    target_vertical: str
    boundary: str
    state: str
    payload_hash: str
    failure_visible: bool
    replay_safe: bool


@dataclass(frozen=True)
class CrossVerticalReconciliationRecord:
    reconciliation_id: str
    run_id: str
    scenario_id: str
    state: str
    blockers: tuple[str, ...]
    observed_steps: tuple[CrossVerticalStepObservation, ...]
    trace_hash: str
    reconciled_at: str
    provider_writes_made: int = 0
    live_actions_made: int = 0


class CrossVerticalReconciliationObservabilityCertification:
    """E3 traceability/reconciliation certification for E2 simulation runs.

    Every simulated handoff must be correlated deterministically, remain visible on failure,
    preserve source/target/boundary/payload lineage and be replay-safe. This layer observes
    and certifies only; it exposes no provider transport or live action path.
    """

    def __init__(self, db_path: str | Path, simulation: CrossVerticalSimulationHarness) -> None:
        self.db_path = str(db_path)
        self.simulation = simulation
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(payload) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS cross_vertical_reconciliations (
                reconciliation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE,
                scenario_id TEXT NOT NULL, state TEXT NOT NULL, blockers_json TEXT NOT NULL,
                trace_hash TEXT NOT NULL, reconciled_at TEXT NOT NULL,
                provider_writes_made INTEGER NOT NULL, live_actions_made INTEGER NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS cross_vertical_step_observations (
                reconciliation_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
                correlation_id TEXT NOT NULL, source_vertical TEXT NOT NULL,
                target_vertical TEXT NOT NULL, boundary TEXT NOT NULL,
                state TEXT NOT NULL, payload_hash TEXT NOT NULL,
                failure_visible INTEGER NOT NULL, replay_safe INTEGER NOT NULL,
                PRIMARY KEY(reconciliation_id, ordinal))''')

    def reconcile_scenario(self, scenario_id: str, *, at: str | None = None) -> CrossVerticalReconciliationRecord:
        run = self.simulation.get_by_scenario(scenario_id)
        if run is None:
            raise CrossVerticalReconciliationError('simulation run not found')
        existing = self.get_by_run(run.run_id)
        if existing is not None:
            return existing

        blockers: list[str] = []
        observations: list[CrossVerticalStepObservation] = []
        canonical: list[dict] = []
        expected_ordinals = list(range(1, len(run.steps) + 1))
        actual_ordinals = [step.ordinal for step in run.steps]
        if actual_ordinals != expected_ordinals:
            blockers.append('non-contiguous-step-order')
        if run.provider_writes_made != 0:
            blockers.append('provider-writes-detected')
        if run.live_actions_made != 0:
            blockers.append('live-actions-detected')

        for step in run.steps:
            if step.state != 'simulated-not-executed':
                blockers.append(f'unexpected-step-state:{step.ordinal}')
            correlation_id = 'xcorr-' + self._hash({
                'run_id': run.run_id, 'ordinal': step.ordinal,
                'source': step.source_vertical, 'target': step.target_vertical,
                'boundary': step.boundary, 'payload_hash': step.payload_hash,
            })[:24]
            failure_visible = bool(step.state)
            replay_safe = bool(step.payload_hash and run.run_hash)
            if not failure_visible:
                blockers.append(f'failure-state-not-visible:{step.ordinal}')
            if not replay_safe:
                blockers.append(f'replay-correlation-incomplete:{step.ordinal}')
            obs = CrossVerticalStepObservation(
                step.ordinal, correlation_id, step.source_vertical, step.target_vertical,
                step.boundary, step.state, step.payload_hash, failure_visible, replay_safe)
            observations.append(obs)
            canonical.append({
                'ordinal': obs.ordinal, 'correlation_id': obs.correlation_id,
                'source_vertical': obs.source_vertical, 'target_vertical': obs.target_vertical,
                'boundary': obs.boundary, 'state': obs.state,
                'payload_hash': obs.payload_hash,
            })

        trace_hash = self._hash({'run_id': run.run_id, 'run_hash': run.run_hash, 'steps': canonical})
        reconciliation_id = 'xrec-' + trace_hash[:24]
        state = 'certified-observable-replay-safe' if not blockers else 'certification-failed'
        record = CrossVerticalReconciliationRecord(
            reconciliation_id, run.run_id, run.scenario_id, state,
            tuple(dict.fromkeys(blockers)), tuple(observations), trace_hash,
            at or self._now(), 0, 0)
        with self._connect() as conn:
            conn.execute('INSERT INTO cross_vertical_reconciliations VALUES (?,?,?,?,?,?,?,?,?)', (
                record.reconciliation_id, record.run_id, record.scenario_id, record.state,
                json.dumps(record.blockers), record.trace_hash, record.reconciled_at, 0, 0))
            for obs in observations:
                conn.execute('INSERT INTO cross_vertical_step_observations VALUES (?,?,?,?,?,?,?,?,?,?)', (
                    record.reconciliation_id, obs.ordinal, obs.correlation_id,
                    obs.source_vertical, obs.target_vertical, obs.boundary, obs.state,
                    obs.payload_hash, int(obs.failure_visible), int(obs.replay_safe)))
        return record

    def get_by_run(self, run_id: str) -> CrossVerticalReconciliationRecord | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM cross_vertical_reconciliations WHERE run_id=?',(run_id,)).fetchone()
            if not row:
                return None
            steps = conn.execute('SELECT * FROM cross_vertical_step_observations WHERE reconciliation_id=? ORDER BY ordinal',(row['reconciliation_id'],)).fetchall()
        observations = tuple(CrossVerticalStepObservation(
            s['ordinal'], s['correlation_id'], s['source_vertical'], s['target_vertical'],
            s['boundary'], s['state'], s['payload_hash'], bool(s['failure_visible']), bool(s['replay_safe']))
            for s in steps)
        return CrossVerticalReconciliationRecord(
            row['reconciliation_id'], row['run_id'], row['scenario_id'], row['state'],
            tuple(json.loads(row['blockers_json'])), observations, row['trace_hash'],
            row['reconciled_at'], row['provider_writes_made'], row['live_actions_made'])
