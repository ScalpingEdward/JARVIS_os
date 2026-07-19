from collections import defaultdict
from math import sqrt
from uuid import UUID

from .models import (
    AuditRecord,
    PortfolioDecision,
    PortfolioHealth,
    PortfolioMetrics,
    PortfolioRun,
    PortfolioRunCreate,
    PortfolioStatus,
    StrategyPortfolioResult,
)


class ExecutivePortfolioIntelligenceService:
    def __init__(self) -> None:
        self._runs: dict[UUID, PortfolioRun] = {}
        self._audit: list[AuditRecord] = []

    def status(self, workspace_id: str) -> PortfolioStatus:
        return PortfolioStatus(
            capabilities=[
                "strategy portfolio construction",
                "correlation and concentration controls",
                "symbol and cluster diversification",
                "advisory weight recommendations",
                "portfolio health and explainability",
                "workspace and account-profile isolation",
            ]
        )

    def create_run(self, payload: PortfolioRunCreate) -> PortfolioRun:
        ranked = sorted(payload.candidates, key=lambda item: item.adaptive_score, reverse=True)
        correlation_map = self._correlation_map(payload)
        symbol_weights: dict[str, float] = defaultdict(float)
        cluster_weights: dict[str, float] = defaultdict(float)
        accepted_ids: list[str] = []
        results: list[StrategyPortfolioResult] = []

        for rank, candidate in enumerate(ranked, start=1):
            reasons: list[str] = []
            decision = PortfolioDecision.INCLUDED
            weight = min(candidate.proposed_weight, payload.policy.max_strategy_weight)

            if not candidate.eligible:
                decision = PortfolioDecision.EXCLUDED
                weight = 0.0
                reasons.append("Strategy is not eligible from adaptive scoring")
            elif candidate.shadow_only:
                decision = PortfolioDecision.SHADOW_ONLY
                weight = 0.0
                reasons.append("Strategy is restricted to shadow mode")
            elif candidate.adaptive_score < payload.policy.minimum_adaptive_score:
                decision = PortfolioDecision.EXCLUDED
                weight = 0.0
                reasons.append("Adaptive score is below portfolio minimum")
            elif candidate.confidence < payload.policy.minimum_confidence:
                decision = PortfolioDecision.SHADOW_ONLY
                weight = 0.0
                reasons.append("Confidence is below portfolio deployment minimum")

            if weight > 0:
                symbol_capacity = payload.policy.max_symbol_weight - symbol_weights[candidate.symbol]
                cluster_capacity = payload.policy.max_cluster_weight - cluster_weights[candidate.asset_cluster]
                allowed = max(0.0, min(weight, symbol_capacity, cluster_capacity))
                if allowed < weight:
                    decision = PortfolioDecision.REDUCED_WEIGHT if allowed > 0 else PortfolioDecision.EXCLUDED
                    reasons.append("Weight reduced by symbol or asset-cluster concentration policy")
                weight = allowed

            if weight > 0:
                high_corr = [
                    other for other in accepted_ids
                    if abs(correlation_map.get(frozenset((candidate.strategy_id, other)), 0.0))
                    >= payload.policy.high_correlation_threshold
                ]
                if high_corr:
                    weight *= 0.5
                    decision = PortfolioDecision.REDUCED_WEIGHT if weight > 0 else PortfolioDecision.EXCLUDED
                    reasons.append("Weight reduced because of high correlation with selected strategy")

            if weight > 0:
                symbol_weights[candidate.symbol] += weight
                cluster_weights[candidate.asset_cluster] += weight
                accepted_ids.append(candidate.strategy_id)
                if candidate.proposed_weight > payload.policy.max_strategy_weight:
                    decision = PortfolioDecision.REDUCED_WEIGHT
                    reasons.append("Weight capped by maximum strategy allocation")
                if not reasons:
                    reasons.append("Strategy passed score, confidence, correlation and concentration checks")

            results.append(
                StrategyPortfolioResult(
                    strategy_id=candidate.strategy_id,
                    strategy_version=candidate.strategy_version,
                    symbol=candidate.symbol,
                    asset_cluster=candidate.asset_cluster,
                    decision=decision,
                    recommended_weight=round(weight, 6),
                    portfolio_rank=rank,
                    score=round(candidate.adaptive_score, 2),
                    reasons=reasons,
                )
            )

        active = [item for item in results if item.recommended_weight > 0]
        total_weight = sum(item.recommended_weight for item in active)
        candidate_by_id = {item.strategy_id: item for item in payload.candidates}
        total_risk = sum(
            candidate_by_id[item.strategy_id].risk_contribution_pct * item.recommended_weight
            for item in active
        )
        weighted_drawdown = sum(
            candidate_by_id[item.strategy_id].expected_drawdown_pct * item.recommended_weight
            for item in active
        )

        symbol_shares = list(symbol_weights.values())
        cluster_shares = list(cluster_weights.values())
        hhi = sum(share * share for share in symbol_shares + cluster_shares) / 2 if active else 1.0
        diversification = max(0.0, min(100.0, (1.0 - hhi) * 125.0))
        concentration = max(0.0, min(100.0, hhi * 100.0))

        corr_values = []
        active_ids = {item.strategy_id for item in active}
        for link in payload.correlations:
            if link.strategy_a in active_ids and link.strategy_b in active_ids:
                corr_values.append(abs(link.correlation))
        correlation_risk = (sum(corr_values) / len(corr_values) * 100.0) if corr_values else 0.0

        if active:
            weighted_confidence = sum(
                candidate_by_id[item.strategy_id].confidence * item.recommended_weight
                for item in active
            ) / max(total_weight, 1e-9)
            scores = [candidate_by_id[item.strategy_id].adaptive_score for item in active]
            mean_score = sum(scores) / len(scores)
            variance = sum((value - mean_score) ** 2 for value in scores) / len(scores)
            stability = max(0.0, 100.0 - sqrt(variance) * 2.0)
        else:
            weighted_confidence = 0.0
            stability = 0.0

        risk_penalty = max(0.0, total_risk - payload.policy.max_total_risk_pct) * 5.0
        drawdown_penalty = max(0.0, weighted_drawdown - payload.policy.max_expected_drawdown_pct) * 5.0
        portfolio_score = max(
            0.0,
            min(100.0, diversification * 0.30 + (100.0 - correlation_risk) * 0.25 + weighted_confidence * 100 * 0.25 + stability * 0.20 - risk_penalty - drawdown_penalty),
        )

        reasons: list[str] = []
        if not active:
            health = PortfolioHealth.BLOCKED
            reasons.append("No strategy passed portfolio construction gates")
        elif total_risk > payload.policy.max_total_risk_pct or weighted_drawdown > payload.policy.max_expected_drawdown_pct:
            health = PortfolioHealth.FRAGILE
            reasons.append("Portfolio exceeds advisory risk or expected drawdown policy")
        elif portfolio_score >= 75:
            health = PortfolioHealth.STRONG
            reasons.append("Portfolio has strong diversification, confidence and stability")
        elif portfolio_score >= 55:
            health = PortfolioHealth.ACCEPTABLE
            reasons.append("Portfolio is acceptable but retains measurable concentration or correlation risk")
        else:
            health = PortfolioHealth.FRAGILE
            reasons.append("Portfolio quality is fragile and should remain advisory or shadow-only")

        run = PortfolioRun(
            workspace_id=payload.workspace_id,
            account_profile_id=payload.account_profile_id,
            actor_id=payload.actor_id,
            health=health,
            metrics=PortfolioMetrics(
                portfolio_score=round(portfolio_score, 2),
                diversification_score=round(diversification, 2),
                concentration_score=round(concentration, 2),
                correlation_risk_score=round(correlation_risk, 2),
                confidence_score=round(weighted_confidence * 100.0, 2),
                stability_score=round(stability, 2),
                total_recommended_weight=round(min(total_weight, 1.0), 6),
                total_risk_contribution_pct=round(total_risk, 4),
                weighted_expected_drawdown_pct=round(weighted_drawdown, 4),
            ),
            results=results,
            reasons=reasons,
        )
        self._runs[run.id] = run
        self._audit.append(
            AuditRecord(
                workspace_id=payload.workspace_id,
                actor_id=payload.actor_id,
                action="portfolio_run_created",
                entity_id=str(run.id),
                details={"account_profile_id": payload.account_profile_id, "health": run.health.value},
            )
        )
        return run

    def list_runs(self, workspace_id: str, account_profile_id: str | None = None) -> list[PortfolioRun]:
        items = [item for item in self._runs.values() if item.workspace_id == workspace_id]
        if account_profile_id:
            items = [item for item in items if item.account_profile_id == account_profile_id]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def get_run(self, run_id: UUID, workspace_id: str) -> PortfolioRun | None:
        item = self._runs.get(run_id)
        return item if item and item.workspace_id == workspace_id else None

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    @staticmethod
    def _correlation_map(payload: PortfolioRunCreate) -> dict[frozenset[str], float]:
        return {frozenset((link.strategy_a, link.strategy_b)): link.correlation for link in payload.correlations}


executive_portfolio_intelligence_service = ExecutivePortfolioIntelligenceService()
