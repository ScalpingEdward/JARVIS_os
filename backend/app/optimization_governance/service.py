from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    ApprovalDecision,
    ApprovalRequest,
    AuditRecord,
    CandidateStatus,
    ConflictRecord,
    GovernanceStatus,
    OptimizationAnalysis,
    OptimizationCandidate,
    OptimizationCandidateCreate,
    RiskLevel,
    SimulationComparison,
    VariantScore,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OptimizationGovernanceService:
    def __init__(self) -> None:
        self._candidates: dict[UUID, OptimizationCandidate] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    def reset(self) -> None:
        with self._lock:
            self._candidates.clear()
            self._audit.clear()

    def status(self, workspace_id: str) -> GovernanceStatus:
        items = self.list_candidates(workspace_id)
        conflicts = sum(len(item.analysis.conflicts) for item in items if item.analysis)
        return GovernanceStatus(
            candidates=len(items),
            pending_approval=sum(item.status == CandidateStatus.pending_approval for item in items),
            approved=sum(item.status == CandidateStatus.approved for item in items),
            rejected=sum(item.status == CandidateStatus.rejected for item in items),
            conflicts=conflicts,
        )

    def create(self, payload: OptimizationCandidateCreate) -> OptimizationCandidate:
        with self._lock:
            duplicate = next(
                (
                    item
                    for item in self._candidates.values()
                    if item.workspace_id == payload.workspace_id
                    and item.target_type == payload.target_type
                    and item.target_id == payload.target_id
                    and item.status not in {CandidateStatus.rejected, CandidateStatus.archived}
                ),
                None,
            )
            if duplicate:
                raise ValueError("Active optimization candidate already exists for target")
            now = _now()
            candidate = OptimizationCandidate(**payload.model_dump(), created_at=now, updated_at=now)
            self._candidates[candidate.id] = candidate
            self._record(payload.workspace_id, "candidate.created", payload.owner_id, candidate.id)
            return candidate

    def list_candidates(self, workspace_id: str) -> list[OptimizationCandidate]:
        return sorted(
            [item for item in self._candidates.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def get(self, candidate_id: UUID, workspace_id: str) -> OptimizationCandidate | None:
        candidate = self._candidates.get(candidate_id)
        return candidate if candidate and candidate.workspace_id == workspace_id else None

    def analyze(self, candidate_id: UUID, workspace_id: str, actor_id: str) -> OptimizationCandidate:
        with self._lock:
            candidate = self._require(candidate_id, workspace_id)
            scores = [self._score_variant(variant) for variant in candidate.variants]
            scores.sort(key=lambda score: score.total_score, reverse=True)
            conflicts = self._detect_conflicts(candidate)
            winner = next(variant for variant in candidate.variants if variant.key == scores[0].variant_key)
            candidate.analysis = OptimizationAnalysis(
                analyzed_at=_now(),
                ranked_variants=scores,
                recommended_variant_key=winner.key,
                conflicts=conflicts,
                rollout_plan=winner.rollout_steps or ["Prepare governed rollout", "Validate KPIs", "Request execution approval"],
                rollback_plan=winner.rollback_steps or ["Stop rollout", "Restore previous configuration", "Validate recovery KPIs"],
            )
            candidate.status = CandidateStatus.pending_approval
            candidate.updated_at = _now()
            self._record(workspace_id, "candidate.analyzed", actor_id, candidate.id, {"winner": winner.key})
            return candidate

    def compare(self, candidate_id: UUID, workspace_id: str, control: str, challenger: str) -> SimulationComparison:
        candidate = self._require(candidate_id, workspace_id)
        if not candidate.analysis:
            raise ValueError("Candidate must be analyzed first")
        score_map = {score.variant_key: score.total_score for score in candidate.analysis.ranked_variants}
        if control not in score_map or challenger not in score_map:
            raise ValueError("Unknown comparison variant")
        delta = round(score_map[challenger] - score_map[control], 4)
        return SimulationComparison(
            candidate_id=candidate.id,
            workspace_id=workspace_id,
            control_variant=control,
            challenger_variant=challenger,
            control_score=score_map[control],
            challenger_score=score_map[challenger],
            expected_delta=delta,
            recommendation=challenger if delta > 0 else control,
            generated_at=_now(),
        )

    def approve(self, candidate_id: UUID, payload: ApprovalRequest) -> OptimizationCandidate:
        with self._lock:
            candidate = self._require(candidate_id, payload.workspace_id)
            if candidate.status != CandidateStatus.pending_approval or not candidate.analysis:
                raise ValueError("Candidate is not pending approval")
            if payload.reviewer_id == candidate.owner_id:
                raise ValueError("Candidate owner cannot approve own optimization")
            if payload.decision == ApprovalDecision.approve:
                selected = payload.variant_key or candidate.analysis.recommended_variant_key
                if selected not in {variant.key for variant in candidate.variants}:
                    raise ValueError("Unknown approval variant")
                candidate.status = CandidateStatus.approved
                candidate.approved_variant_key = selected
            else:
                candidate.status = CandidateStatus.rejected
                candidate.approved_variant_key = None
            candidate.approved_by = payload.reviewer_id
            candidate.approval_reason = payload.reason
            candidate.updated_at = _now()
            self._record(
                payload.workspace_id,
                f"candidate.{candidate.status.value}",
                payload.reviewer_id,
                candidate.id,
                {"variant": candidate.approved_variant_key, "automatic_application": False},
            )
            return candidate

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def _score_variant(self, variant) -> VariantScore:
        if variant.metric_impacts:
            weighted_gain = sum((impact.expected - impact.baseline) * impact.weight for impact in variant.metric_impacts)
            total_weight = sum(impact.weight for impact in variant.metric_impacts)
            expected_gain = weighted_gain / total_weight
        else:
            expected_gain = 0.0
        risk_map = {RiskLevel.low: 0.15, RiskLevel.medium: 0.35, RiskLevel.high: 0.65, RiskLevel.critical: 0.9}
        risk_score = risk_map[variant.risk_level]
        cost_score = min(1.0, (variant.implementation_cost / 100000) + (variant.estimated_hours / 1000))
        roi_score = expected_gain / max(1.0, variant.implementation_cost + variant.estimated_hours)
        confidence = max(0.1, min(0.99, 0.55 + 0.05 * len(variant.metric_impacts) - 0.2 * risk_score))
        total = expected_gain * 0.5 + roi_score * 0.25 + confidence * 0.25 - risk_score * 0.35 - cost_score * 0.2
        return VariantScore(
            variant_key=variant.key,
            expected_gain=round(expected_gain, 4),
            risk_score=round(risk_score, 4),
            cost_score=round(cost_score, 4),
            roi_score=round(roi_score, 6),
            confidence=round(confidence, 4),
            total_score=round(total, 4),
            explanation=[
                f"Expected weighted KPI gain: {expected_gain:.4f}",
                f"Risk penalty: {risk_score:.2f}",
                f"Cost and effort penalty: {cost_score:.2f}",
                "Recommendation remains advisory until independent human approval.",
            ],
        )

    def _detect_conflicts(self, candidate: OptimizationCandidate) -> list[ConflictRecord]:
        records: list[ConflictRecord] = []
        for key in candidate.conflict_keys:
            matching = [
                item.id
                for item in self._candidates.values()
                if item.workspace_id == candidate.workspace_id
                and item.id != candidate.id
                and key in item.conflict_keys
                and item.status in {CandidateStatus.pending_approval, CandidateStatus.approved}
            ]
            if matching:
                records.append(
                    ConflictRecord(
                        conflict_key=key,
                        candidate_ids=[candidate.id, *matching],
                        severity=RiskLevel.high,
                        explanation=f"Multiple active optimizations modify governed resource '{key}'.",
                    )
                )
        return records

    def _require(self, candidate_id: UUID, workspace_id: str) -> OptimizationCandidate:
        candidate = self.get(candidate_id, workspace_id)
        if not candidate:
            raise KeyError("Optimization candidate not found")
        return candidate

    def _record(
        self,
        workspace_id: str,
        action: str,
        actor_id: str,
        candidate_id: UUID | None = None,
        details: dict | None = None,
    ) -> None:
        self._audit.append(
            AuditRecord(
                workspace_id=workspace_id,
                action=action,
                actor_id=actor_id,
                candidate_id=candidate_id,
                details=details or {},
                created_at=_now(),
            )
        )


optimization_governance_service = OptimizationGovernanceService()
