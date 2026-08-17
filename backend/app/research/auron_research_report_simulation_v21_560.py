from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.research.auron_research_evidence_policy_v21_559 import ResearchEvidenceProvenanceConfidencePolicy
from app.research.auron_research_registry_evidence_v21_557 import ResearchRegistryEvidenceStore


class ResearchReportSimulationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchCitationRef:
    citation_id: str
    result_id: str
    source_id: str
    canonical_url: str
    title: str
    attribution: str
    evidence_hash: str
    confidence: str
    score: float


@dataclass(frozen=True)
class ResearchReportSimulation:
    report_id: str
    query_id: str
    minimum_confidence: str
    state: str
    evidence_count: int
    body_markdown: str
    citations: tuple[ResearchCitationRef, ...]
    report_hash: str
    created_at: str
    downstream_execution_enabled: bool = False
    external_calls_made: int = 0


class ResearchReportSimulationService:
    """D13 deterministic, local-only research report assembly.

    Only D12-admissible evidence is included. The report contains explicit citation
    references bound to the exact stored evidence hash. This layer performs no provider
    calls, recurring watches, publishing, messaging or trading actions.
    """

    def __init__(self, db_path: str | Path, store: ResearchRegistryEvidenceStore,
                 policy: ResearchEvidenceProvenanceConfidencePolicy) -> None:
        self.db_path = str(db_path)
        self.store = store
        self.policy = policy
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
            conn.execute('''CREATE TABLE IF NOT EXISTS research_report_simulations (
                report_id TEXT PRIMARY KEY, query_id TEXT NOT NULL,
                minimum_confidence TEXT NOT NULL, state TEXT NOT NULL,
                evidence_count INTEGER NOT NULL, body_markdown TEXT NOT NULL,
                citations_json TEXT NOT NULL, report_hash TEXT NOT NULL,
                created_at TEXT NOT NULL, downstream_execution_enabled INTEGER NOT NULL,
                external_calls_made INTEGER NOT NULL)''')

    @staticmethod
    def _report_id(query_id: str, minimum_confidence: str, evidence_fingerprint: str) -> str:
        raw = f'{query_id}\x1f{minimum_confidence}\x1f{evidence_fingerprint}'.encode()
        return 'report-' + hashlib.sha256(raw).hexdigest()[:24]

    def assemble(self, query_id: str, *, minimum_confidence: str = 'medium',
                 now: str | None = None) -> ResearchReportSimulation:
        query = self.store.get_query(query_id)
        if query is None:
            raise ResearchReportSimulationError('query not found')
        admissible = self.policy.admissible_evidence(query_id, minimum_confidence=minimum_confidence, now=now)
        if not admissible:
            raise ResearchReportSimulationError('no admissible evidence for report simulation')

        result_by_id = {item.result_id: item for item in self.store.list_results(query_id)}
        citations: list[ResearchCitationRef] = []
        sections: list[str] = [f'# Research simulation: {query.query_text}', '', 'Simulation only. No downstream action is authorized.', '']

        ordered = sorted(admissible, key=lambda item: (-item.score, item.result_id))
        for index, assessment in enumerate(ordered, start=1):
            result = result_by_id[assessment.result_id]
            source = self.store.get_source(assessment.source_id)
            if source is None:
                raise ResearchReportSimulationError('source disappeared during assembly')
            citation_id = f'R{index}'
            citations.append(ResearchCitationRef(
                citation_id=citation_id,
                result_id=result.result_id,
                source_id=source.source_id,
                canonical_url=source.canonical_url,
                title=source.title,
                attribution=source.attribution,
                evidence_hash=result.evidence_hash,
                confidence=assessment.confidence,
                score=assessment.score,
            ))
            sections.extend([
                f'## Evidence {index}',
                f'{result.snippet} [{citation_id}]',
                f'Confidence policy: {assessment.confidence} ({assessment.score:.2f})',
                '',
            ])

        sections.extend(['## References'])
        for citation in citations:
            sections.append(f'[{citation.citation_id}] {citation.title} — {citation.attribution} — {citation.canonical_url}')
        body = '\n'.join(sections).strip() + '\n'

        fingerprint_payload = json.dumps([
            {'result_id': c.result_id, 'source_id': c.source_id, 'evidence_hash': c.evidence_hash,
             'confidence': c.confidence, 'score': c.score}
            for c in citations
        ], sort_keys=True, separators=(',', ':'))
        evidence_fingerprint = hashlib.sha256(fingerprint_payload.encode()).hexdigest()
        report_id = self._report_id(query_id, minimum_confidence, evidence_fingerprint)
        report_hash = hashlib.sha256(body.encode()).hexdigest()
        existing = self.get(report_id)
        if existing is not None:
            return existing

        report = ResearchReportSimulation(
            report_id=report_id,
            query_id=query_id,
            minimum_confidence=minimum_confidence,
            state='simulated-report-ready',
            evidence_count=len(citations),
            body_markdown=body,
            citations=tuple(citations),
            report_hash=report_hash,
            created_at=now or self._now(),
            downstream_execution_enabled=False,
            external_calls_made=0,
        )
        with self._connect() as conn:
            conn.execute('INSERT INTO research_report_simulations VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
                report.report_id, report.query_id, report.minimum_confidence, report.state,
                report.evidence_count, report.body_markdown,
                json.dumps([asdict(item) for item in report.citations], sort_keys=True),
                report.report_hash, report.created_at, int(report.downstream_execution_enabled),
                report.external_calls_made,
            ))
        return report

    def get(self, report_id: str) -> ResearchReportSimulation | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM research_report_simulations WHERE report_id=?', (report_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['citations'] = tuple(ResearchCitationRef(**item) for item in json.loads(data.pop('citations_json')))
        data['downstream_execution_enabled'] = bool(data['downstream_execution_enabled'])
        return ResearchReportSimulation(**data)

    def list_reports(self, query_id: str) -> tuple[ResearchReportSimulation, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT report_id FROM research_report_simulations WHERE query_id=? ORDER BY created_at,report_id', (query_id,)).fetchall()
        return tuple(self.get(row['report_id']) for row in rows)
