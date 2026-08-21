from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.research.auron_research_network_transport_authorization_v21_613 import (
    ResearchNetworkTransportAuthorizationDecision,
)
from app.research.auron_research_readonly_network_transport_boundary_v21_614 import (
    ResearchReadonlyNetworkTransportBoundary,
    ResearchReadonlyNetworkBoundaryError,
)


class ResearchReadonlyNetworkE2ECertificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchReadonlyNetworkE2ECertification:
    certification_id: str
    decision_id: str
    activation_id: str
    status: str
    blockers: tuple[str, ...]
    calls_observed: int
    provider_writes_observed: int
    budget_enforced: bool
    stop_enforced: bool
    real_provider_transport_used: bool
    certified_at: str


class ResearchReadonlyNetworkBoundaryE2ECertifier:
    """H7 certifies H5 -> H6 using deterministic injected fakes only."""

    def __init__(self, db_path: str | Path, boundary: ResearchReadonlyNetworkTransportBoundary) -> None:
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.boundary = boundary
        self._init_schema()

    def _connect(self):
        c = sqlite3.connect(self.db_path); c.row_factory = sqlite3.Row; return c

    def _init_schema(self):
        with self._connect() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS research_network_e2e_certifications(
                certification_id TEXT PRIMARY KEY,decision_id TEXT NOT NULL,activation_id TEXT NOT NULL,
                status TEXT NOT NULL,blockers_json TEXT NOT NULL,calls_observed INTEGER NOT NULL,
                provider_writes_observed INTEGER NOT NULL,budget_enforced INTEGER NOT NULL,
                stop_enforced INTEGER NOT NULL,real_provider_transport_used INTEGER NOT NULL,
                certified_at TEXT NOT NULL)''')

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(v): return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def certify(self, decision: ResearchNetworkTransportAuthorizationDecision, *, endpoint: str,
                max_requests: int = 2, timeout_seconds: int = 5) -> ResearchReadonlyNetworkE2ECertification:
        blockers=[]
        if not decision.authorized: blockers.append('h5-decision-not-authorized')
        if not decision.requires_separate_activation: blockers.append('h5-separate-activation-not-required')
        if any((decision.network_transport_enabled, decision.credential_resolution_enabled,
                decision.provider_write_enabled, decision.production_transport_enabled)):
            blockers.append('h5-preactivation-safety-violated')
        if self.boundary.resolver is None or self.boundary.transport is None:
            blockers.append('deterministic-fake-boundary-dependencies-required')
        if blockers:
            raise ResearchReadonlyNetworkE2ECertificationError(','.join(blockers))

        activation=self.boundary.arm(decision,max_requests=max_requests,timeout_seconds=timeout_seconds)
        calls=[]
        for _ in range(max_requests):
            calls.append(self.boundary.execute_get(activation_id=activation.activation_id,endpoint=endpoint,kill_switch_active=True))

        budget_enforced=False
        try:
            self.boundary.execute_get(activation_id=activation.activation_id,endpoint=endpoint,kill_switch_active=True)
        except ResearchReadonlyNetworkBoundaryError:
            budget_enforced=True
        after_budget=self.boundary.activation(activation.activation_id)
        stop_enforced=after_budget is not None and not after_budget.active

        writes=sum(1 for c in calls if c.provider_write_performed)
        if len(calls)!=max_requests: blockers.append('request-accounting-mismatch')
        if any(c.external_calls_made!=1 for c in calls): blockers.append('call-accounting-mismatch')
        if writes: blockers.append('provider-write-observed')
        if not budget_enforced: blockers.append('request-budget-not-enforced')
        if not stop_enforced: blockers.append('budget-stop-not-enforced')

        # H7 deliberately certifies only an injected deterministic test transport. It does not
        # attest to, configure, or authorize any real provider client or production endpoint.
        real_provider_transport_used=False
        status='certified' if not blockers else 'blocked'; now=self._now()
        cid='research-network-e2e-'+self._hash({'decision':decision.decision_id,'activation':activation.activation_id,'endpoint':endpoint})[:24]
        with self._connect() as c:
            c.execute('INSERT OR IGNORE INTO research_network_e2e_certifications VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (cid,decision.decision_id,activation.activation_id,status,json.dumps(blockers),len(calls),writes,
                 int(budget_enforced),int(stop_enforced),0,now))
        return ResearchReadonlyNetworkE2ECertification(cid,decision.decision_id,activation.activation_id,status,
            tuple(blockers),len(calls),writes,budget_enforced,stop_enforced,real_provider_transport_used,now)
