from collections import defaultdict
from math import exp
from uuid import UUID

from .models import (
    AuditRecord,
    CandidateEvidenceUpdate,
    CandidateRole,
    ChampionChallengerStatusResponse,
    ComparisonCreate,
    EvaluationDecision,
    PromotionResult,
    StrategyCandidate,
    StrategyCandidateCreate,
    StrategyComparison,
    utc_now,
)


class ExecutiveChampionChallengerService:
    def __init__(self) -> None:
        self._candidates: dict[UUID, StrategyCandidate] = {}
        self._comparisons: dict[UUID, StrategyComparison] = {}
        self._audit: dict[str, list[AuditRecord]] = defaultdict(list)

    def status(self, workspace_id: str) -> ChampionChallengerStatusResponse:
        return ChampionChallengerStatusResponse(
            workspace_id=workspace_id,
            candidate_count=len(self.list_candidates(workspace_id)),
            comparison_count=len(self.list_comparisons(workspace_id)),
        )

    def create_candidate(self, payload: StrategyCandidateCreate) -> StrategyCandidate:
        for candidate in self._candidates.values():
            if (
                candidate.workspace_id == payload.workspace_id
                and candidate.account_profile_id == payload.account_profile_id
                and candidate.strategy_id == payload.strategy_id
                and candidate.strategy_version == payload.strategy_version
            ):
                raise ValueError("Strategy candidate already exists for this account profile")
        if payload.role == CandidateRole.CHAMPION and self._champion(payload.workspace_id, payload.account_profile_id):
            raise ValueError("Account profile already has a champion")
        candidate = StrategyCandidate(**payload.model_dump(exclude={"actor_id"}))
        self._candidates[candidate.id] = candidate
        self._record(payload.workspace_id, payload.actor_id, "candidate.created", candidate.id, {"role": candidate.role.value})
        return candidate

    def get_candidate(self, candidate_id: UUID, workspace_id: str) -> StrategyCandidate | None:
        candidate = self._candidates.get(candidate_id)
        return candidate if candidate and candidate.workspace_id == workspace_id else None

    def list_candidates(self, workspace_id: str, account_profile_id: str | None = None) -> list[StrategyCandidate]:
        return [
            candidate for candidate in self._candidates.values()
            if candidate.workspace_id == workspace_id
            and (account_profile_id is None or candidate.account_profile_id == account_profile_id)
        ]

    def update_evidence(self, candidate_id: UUID, workspace_id: str, payload: CandidateEvidenceUpdate) -> StrategyCandidate:
        candidate = self.get_candidate(candidate_id, workspace_id)
        if candidate is None:
            raise KeyError("Strategy candidate not found")
        candidate.evidence = payload.evidence
        candidate.updated_at = utc_now()
        self._record(workspace_id, payload.actor_id, "candidate.evidence_updated", candidate.id, {"sample_size": payload.evidence.sample_size})
        return candidate

    def compare(self, payload: ComparisonCreate) -> StrategyComparison:
        champion = self.get_candidate(payload.champion_id, payload.workspace_id)
        challenger = self.get_candidate(payload.challenger_id, payload.workspace_id)
        if champion is None or challenger is None:
            raise KeyError("Champion or challenger not found")
        if champion.account_profile_id != payload.account_profile_id or challenger.account_profile_id != payload.account_profile_id:
            raise ValueError("Candidates must belong to the requested account profile")
        if champion.role != CandidateRole.CHAMPION:
            raise ValueError("Selected champion candidate is not the active champion")
        if challenger.role != CandidateRole.CHALLENGER:
            raise ValueError("Selected challenger candidate is not an active challenger")

        ce, he, policy = champion.evidence, challenger.evidence, payload.policy
        pf_uplift = he.profit_factor - ce.profit_factor
        expectancy_uplift = he.expectancy_r - ce.expectancy_r
        drawdown_change = he.max_drawdown_pct - ce.max_drawdown_pct
        reasons: list[str] = []

        sufficient = ce.sample_size >= policy.minimum_sample_size and he.sample_size >= policy.minimum_sample_size
        if not sufficient:
            decision = EvaluationDecision.INSUFFICIENT_EVIDENCE
            reasons.append("Minimum sample size not reached by both candidates")
        else:
            if pf_uplift < policy.minimum_profit_factor_uplift:
                reasons.append("Profit-factor uplift below policy threshold")
            if expectancy_uplift < policy.minimum_expectancy_uplift_r:
                reasons.append("Expectancy uplift below policy threshold")
            if drawdown_change > policy.maximum_drawdown_increase_pct:
                reasons.append("Drawdown increase exceeds policy threshold")
            if he.confidence_calibration_error > policy.maximum_calibration_error:
                reasons.append("Challenger confidence calibration is insufficient")
            decision = EvaluationDecision.PROMOTION_RECOMMENDED if not reasons else EvaluationDecision.KEEP_CHAMPION

        evidence_strength = min(1.0, min(ce.sample_size, he.sample_size) / max(policy.minimum_sample_size * 4, 1))
        edge_strength = 1 / (1 + exp(-4 * (pf_uplift + expectancy_uplift)))
        confidence = round(min(0.999, 0.5 + 0.35 * evidence_strength + 0.149 * edge_strength), 4)
        if decision == EvaluationDecision.PROMOTION_RECOMMENDED and confidence < policy.required_confidence:
            decision = EvaluationDecision.KEEP_CHAMPION
            reasons.append("Comparison confidence below promotion threshold")
        if decision == EvaluationDecision.PROMOTION_RECOMMENDED:
            reasons.append("Challenger satisfies all governed promotion thresholds")

        comparison = StrategyComparison(
            workspace_id=payload.workspace_id,
            account_profile_id=payload.account_profile_id,
            champion_id=champion.id,
            challenger_id=challenger.id,
            policy=policy,
            decision=decision,
            confidence=confidence,
            reasons=reasons,
            profit_factor_uplift=round(pf_uplift, 4),
            expectancy_uplift_r=round(expectancy_uplift, 4),
            drawdown_change_pct=round(drawdown_change, 4),
        )
        self._comparisons[comparison.id] = comparison
        self._record(payload.workspace_id, payload.actor_id, "comparison.created", comparison.id, {"decision": decision.value, "confidence": confidence})
        return comparison

    def list_comparisons(self, workspace_id: str) -> list[StrategyComparison]:
        return [item for item in self._comparisons.values() if item.workspace_id == workspace_id]

    def promote(self, workspace_id: str, comparison_id: UUID, actor_id: str) -> PromotionResult:
        comparison = self._comparisons.get(comparison_id)
        if comparison is None or comparison.workspace_id != workspace_id:
            raise KeyError("Strategy comparison not found")
        if comparison.decision != EvaluationDecision.PROMOTION_RECOMMENDED:
            return PromotionResult(promoted=False, former_champion_id=comparison.champion_id, reason="Promotion was not recommended")
        champion = self._candidates[comparison.champion_id]
        challenger = self._candidates[comparison.challenger_id]
        champion.role = CandidateRole.RETIRED
        challenger.role = CandidateRole.CHAMPION
        champion.updated_at = challenger.updated_at = utc_now()
        self._record(workspace_id, actor_id, "challenger.promoted", challenger.id, {"former_champion_id": str(champion.id)})
        return PromotionResult(promoted=True, former_champion_id=champion.id, new_champion_id=challenger.id, reason="Manual governed promotion completed")

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return list(self._audit.get(workspace_id, []))

    def _champion(self, workspace_id: str, account_profile_id: str) -> StrategyCandidate | None:
        return next((c for c in self._candidates.values() if c.workspace_id == workspace_id and c.account_profile_id == account_profile_id and c.role == CandidateRole.CHAMPION), None)

    def _record(self, workspace_id: str, actor_id: str, action: str, entity_id: UUID, details: dict) -> None:
        self._audit[workspace_id].append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, entity_id=entity_id, details=details))


executive_champion_challenger_service = ExecutiveChampionChallengerService()
