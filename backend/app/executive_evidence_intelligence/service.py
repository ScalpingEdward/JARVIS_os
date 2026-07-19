from math import sqrt
from statistics import fmean, pstdev
from uuid import UUID

from .models import (
    AuditRecord,
    EvidenceAssessment,
    EvidenceComparison,
    EvidenceComparisonCreate,
    EvidenceMetrics,
    EvidenceObservation,
    EvidenceObservationCreate,
    EvidenceQuery,
    EvidenceStatusResponse,
    EvidenceVerdict,
    ReliabilityBand,
)


class ExecutiveEvidenceIntelligenceService:
    def __init__(self) -> None:
        self._observations: dict[UUID, EvidenceObservation] = {}
        self._assessments: dict[UUID, EvidenceAssessment] = {}
        self._comparisons: dict[UUID, EvidenceComparison] = {}
        self._audit: list[AuditRecord] = []

    def reset(self) -> None:
        self._observations.clear()
        self._assessments.clear()
        self._comparisons.clear()
        self._audit.clear()

    def status(self, workspace_id: str) -> EvidenceStatusResponse:
        return EvidenceStatusResponse(
            workspace_id=workspace_id,
            observation_count=len(self.list_observations(workspace_id)),
            assessment_count=len(self.list_assessments(workspace_id)),
            comparison_count=len(self.list_comparisons(workspace_id)),
        )

    def record_observation(self, payload: EvidenceObservationCreate) -> EvidenceObservation:
        duplicate = next(
            (
                item
                for item in self._observations.values()
                if item.workspace_id == payload.workspace_id
                and item.source == payload.source
                and item.source_reference == payload.source_reference
            ),
            None,
        )
        if duplicate is not None:
            raise ValueError("Evidence source reference already recorded in this workspace")
        observation = EvidenceObservation(**payload.model_dump())
        self._observations[observation.id] = observation
        self._log(payload.workspace_id, payload.actor_id, "record", "evidence_observation", str(observation.id), {
            "source": observation.source.value,
            "source_reference": observation.source_reference,
            "strategy_id": observation.context.strategy_id,
            "realized_r": observation.realized_r,
        })
        return observation

    def get_observation(self, observation_id: UUID, workspace_id: str) -> EvidenceObservation | None:
        item = self._observations.get(observation_id)
        return item if item is not None and item.workspace_id == workspace_id else None

    def list_observations(self, workspace_id: str) -> list[EvidenceObservation]:
        return sorted(
            [item for item in self._observations.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
        )

    def assess(self, query: EvidenceQuery, actor_id: str) -> EvidenceAssessment:
        matching = [item for item in self.list_observations(query.workspace_id) if self._matches(item, query)]
        metrics = self._metrics(matching)
        reasons: list[str] = []
        if metrics.sample_size < query.minimum_sample:
            verdict = EvidenceVerdict.INSUFFICIENT
            reasons.append(f"Sample {metrics.sample_size} is below minimum {query.minimum_sample}")
        elif metrics.expectancy_r >= 0.10 and metrics.profit_factor is not None and metrics.profit_factor >= 1.20:
            verdict = EvidenceVerdict.POSITIVE
            reasons.append("Positive expectancy and profit factor clear the evidence threshold")
        elif metrics.expectancy_r <= -0.10:
            verdict = EvidenceVerdict.NEGATIVE
            reasons.append("Negative expectancy indicates adverse historical evidence")
        else:
            verdict = EvidenceVerdict.NEUTRAL
            reasons.append("Observed edge is too small for a directional conclusion")
        reliability = self._reliability(metrics.sample_size, metrics.confidence_calibration_error)
        score = self._score(metrics, query.minimum_sample)
        assessment = EvidenceAssessment(
            workspace_id=query.workspace_id,
            query=query,
            metrics=metrics,
            verdict=verdict,
            reliability=reliability,
            evidence_score=score,
            reasons=reasons,
        )
        self._assessments[assessment.id] = assessment
        self._log(query.workspace_id, actor_id, "assess", "evidence_assessment", str(assessment.id), {
            "sample_size": metrics.sample_size,
            "verdict": verdict.value,
            "reliability": reliability.value,
            "evidence_score": score,
        })
        return assessment

    def compare(self, payload: EvidenceComparisonCreate) -> EvidenceComparison:
        baseline = self.assess(payload.baseline_query, payload.actor_id)
        candidate = self.assess(payload.candidate_query, payload.actor_id)
        reasons: list[str] = []
        edge = round(candidate.metrics.expectancy_r - baseline.metrics.expectancy_r, 6)
        enough_sample = (
            baseline.metrics.sample_size >= payload.minimum_sample
            and candidate.metrics.sample_size >= payload.minimum_sample
        )
        calibration_delta = candidate.metrics.confidence_calibration_error - baseline.metrics.confidence_calibration_error
        if not enough_sample:
            recommendation = "insufficient_evidence"
            reasons.append("Both cohorts must satisfy the comparison minimum sample")
        elif edge < payload.minimum_expectancy_edge_r:
            recommendation = "keep_baseline"
            reasons.append("Candidate expectancy edge is below the governed threshold")
        elif calibration_delta > payload.maximum_calibration_degradation:
            recommendation = "keep_baseline"
            reasons.append("Candidate confidence calibration degrades beyond policy")
        elif candidate.verdict != EvidenceVerdict.POSITIVE:
            recommendation = "keep_baseline"
            reasons.append("Candidate evidence is not independently positive")
        else:
            recommendation = "candidate_supported"
            reasons.append("Candidate clears sample, expectancy and calibration gates")
        confidence = min(baseline.evidence_score, candidate.evidence_score)
        comparison = EvidenceComparison(
            workspace_id=payload.workspace_id,
            actor_id=payload.actor_id,
            baseline=baseline,
            candidate=candidate,
            candidate_edge_r=edge,
            recommendation=recommendation,
            confidence=confidence,
            reasons=reasons,
        )
        self._comparisons[comparison.id] = comparison
        self._log(payload.workspace_id, payload.actor_id, "compare", "evidence_comparison", str(comparison.id), {
            "candidate_edge_r": edge,
            "recommendation": recommendation,
            "confidence": confidence,
        })
        return comparison

    def list_assessments(self, workspace_id: str) -> list[EvidenceAssessment]:
        return sorted(
            [item for item in self._assessments.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
        )

    def list_comparisons(self, workspace_id: str) -> list[EvidenceComparison]:
        return sorted(
            [item for item in self._comparisons.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    @staticmethod
    def _matches(item: EvidenceObservation, query: EvidenceQuery) -> bool:
        context = item.context
        scalar_filters = {
            "strategy_id": query.strategy_id,
            "account_profile": query.account_profile,
            "symbol": query.symbol,
            "timeframe": query.timeframe,
            "market_regime": query.market_regime,
            "session": query.session,
        }
        for field, expected in scalar_filters.items():
            if expected is not None and getattr(context, field) != expected:
                return False
        return all(context.factors.get(key) == value for key, value in query.factor_filters.items())

    @staticmethod
    def _metrics(items: list[EvidenceObservation]) -> EvidenceMetrics:
        if not items:
            return EvidenceMetrics()
        realized = [item.realized_r for item in items]
        wins = sum(1 for item in items if item.won)
        losses = len(items) - wins
        gross_profit = sum(value for value in realized if value > 0)
        gross_loss = abs(sum(value for value in realized if value < 0))
        profit_factor = None if gross_loss == 0 else round(gross_profit / gross_loss, 6)
        mfe_values = [item.max_favorable_excursion_r for item in items if item.max_favorable_excursion_r is not None]
        mae_values = [item.max_adverse_excursion_r for item in items if item.max_adverse_excursion_r is not None]
        calibration = fmean(abs(item.confidence_at_decision - (1.0 if item.won else 0.0)) for item in items)
        std_error = None if len(realized) < 2 else pstdev(realized) / sqrt(len(realized))
        average_r = fmean(realized)
        return EvidenceMetrics(
            sample_size=len(items),
            wins=wins,
            losses=losses,
            win_rate=round(wins / len(items), 6),
            average_r=round(average_r, 6),
            expectancy_r=round(average_r, 6),
            profit_factor=profit_factor,
            average_mfe_r=None if not mfe_values else round(fmean(mfe_values), 6),
            average_mae_r=None if not mae_values else round(fmean(mae_values), 6),
            confidence_calibration_error=round(calibration, 6),
            standard_error_r=None if std_error is None else round(std_error, 6),
        )

    @staticmethod
    def _reliability(sample_size: int, calibration_error: float) -> ReliabilityBand:
        if sample_size >= 1000 and calibration_error <= 0.10:
            return ReliabilityBand.VERY_HIGH
        if sample_size >= 250 and calibration_error <= 0.20:
            return ReliabilityBand.HIGH
        if sample_size >= 50 and calibration_error <= 0.30:
            return ReliabilityBand.MODERATE
        return ReliabilityBand.LOW

    @staticmethod
    def _score(metrics: EvidenceMetrics, minimum_sample: int) -> float:
        sample_component = min(1.0, metrics.sample_size / max(1, minimum_sample * 4))
        calibration_component = max(0.0, 1.0 - metrics.confidence_calibration_error)
        precision_component = 0.0 if metrics.standard_error_r is None else max(0.0, 1.0 - min(1.0, metrics.standard_error_r))
        return round((sample_component * 0.45) + (calibration_component * 0.35) + (precision_component * 0.20), 6)

    def _log(self, workspace_id: str, actor_id: str, action: str, entity_type: str, entity_id: str, details: dict) -> None:
        self._audit.append(AuditRecord(
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        ))


executive_evidence_intelligence_service = ExecutiveEvidenceIntelligenceService()
