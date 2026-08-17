from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from app.research.auron_research_registry_evidence_v21_557 import ResearchRegistryEvidenceStore

ConfidenceBand = Literal['high', 'medium', 'low', 'rejected']


class ResearchEvidencePolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class EvidenceAssessment:
    assessment_id: str
    query_id: str
    result_id: str
    source_id: str
    admissible: bool
    confidence: ConfidenceBand
    score: float
    blockers: tuple[str, ...]
    freshness_state: str
    provenance_verified: bool
    evidence_integrity_verified: bool
    attribution_verified: bool


class ResearchEvidenceProvenanceConfidencePolicy:
    """D12 fail-closed evidence admission policy.

    Evidence is admissible only when query/result/source lineage is intact, the stored
    evidence hash still matches the current source content, attribution exists and the
    source is not stale. Confidence is a transparent policy score, not a truth claim.
    """

    def __init__(self, store: ResearchRegistryEvidenceStore) -> None:
        self.store = store

    @staticmethod
    def _assessment_id(query_id: str, result_id: str, source_hash: str) -> str:
        raw = f'{query_id}\x1f{result_id}\x1f{source_hash}'.encode()
        return 'assess-' + hashlib.sha256(raw).hexdigest()[:24]

    @staticmethod
    def _expected_evidence_hash(content_hash: str, snippet: str) -> str:
        return hashlib.sha256(f'{content_hash}\x1f{snippet.strip()}'.encode()).hexdigest()

    def assess(self, query_id: str, result_id: str, *, now: str | None = None) -> EvidenceAssessment:
        query = self.store.get_query(query_id)
        if query is None:
            raise ResearchEvidencePolicyError('query not found')
        result = next((item for item in self.store.list_results(query_id) if item.result_id == result_id), None)
        if result is None:
            raise ResearchEvidencePolicyError('result not found for query')
        source = self.store.get_source(result.source_id)
        if source is None:
            raise ResearchEvidencePolicyError('source not found')

        blockers: list[str] = []
        provenance = result.query_id == query.query_id and query.provider_id == source.provider_id
        if not provenance:
            blockers.append('provenance-mismatch')

        expected_hash = self._expected_evidence_hash(source.content_hash, result.snippet)
        integrity = result.evidence_hash == expected_hash
        if not integrity:
            blockers.append('evidence-integrity-mismatch')

        attribution = bool(source.attribution.strip())
        if not attribution:
            blockers.append('source-attribution-missing')

        freshness = self.store.evidence_state(source.source_id, now=now)
        if freshness.freshness_state == 'stale':
            blockers.append('source-evidence-stale')

        score = 1.0
        if freshness.freshness_state == 'aging':
            score -= 0.20
        if not source.publisher:
            score -= 0.10
        if not source.published_at:
            score -= 0.10
        if result.rank > 3:
            score -= 0.10
        if blockers:
            score = min(score, 0.39)
        score = round(max(0.0, min(1.0, score)), 2)

        if blockers:
            band: ConfidenceBand = 'rejected'
        elif score >= 0.80:
            band = 'high'
        elif score >= 0.60:
            band = 'medium'
        else:
            band = 'low'

        return EvidenceAssessment(
            assessment_id=self._assessment_id(query_id, result_id, source.content_hash),
            query_id=query_id,
            result_id=result_id,
            source_id=source.source_id,
            admissible=not blockers,
            confidence=band,
            score=score,
            blockers=tuple(dict.fromkeys(blockers)),
            freshness_state=freshness.freshness_state,
            provenance_verified=provenance,
            evidence_integrity_verified=integrity,
            attribution_verified=attribution,
        )

    def admissible_evidence(self, query_id: str, *, minimum_confidence: ConfidenceBand = 'medium',
                            now: str | None = None) -> tuple[EvidenceAssessment, ...]:
        thresholds = {'low': 0.0, 'medium': 0.60, 'high': 0.80, 'rejected': 2.0}
        threshold = thresholds[minimum_confidence]
        assessments = tuple(self.assess(query_id, result.result_id, now=now) for result in self.store.list_results(query_id))
        return tuple(item for item in assessments if item.admissible and item.score >= threshold)
