from uuid import UUID

from .models import (
    CoachAction,
    CoachPriority,
    PlaybookCreate,
    StrategyCoachStatus,
    StrategyPlaybook,
)


class StrategyCoachService:
    def __init__(self) -> None:
        self._playbooks: dict[UUID, StrategyPlaybook] = {}

    def status(self) -> StrategyCoachStatus:
        return StrategyCoachStatus()

    def create(self, payload: PlaybookCreate) -> StrategyPlaybook:
        score = self._readiness_score(payload)
        actions = self._actions(payload)
        checklist = [
            "Confirm H4/H1 directional bias and market structure.",
            "Confirm liquidity sweep or displacement before entry.",
            "Use only an approved setup from this playbook.",
            "Define entry, invalidation, stop loss and take profit before approval.",
            "Check spread, news window, daily drawdown and open exposure.",
            "MASTER Brano must approve the trade manually.",
        ]
        for mistake in self._normalize(payload.recurring_mistakes)[:5]:
            checklist.append(f"Reject the trade if '{mistake}' is present.")
        playbook = StrategyPlaybook(
            name=payload.name.strip(),
            symbol=payload.symbol.upper(),
            timeframe=payload.timeframe.upper(),
            readiness_score=score,
            approved_setups=self._normalize(payload.best_setups),
            blocked_mistakes=self._normalize(payload.recurring_mistakes),
            pre_trade_checklist=checklist,
            improvement_actions=actions,
            live_use_recommended=score >= 80 and not payload.recurring_mistakes,
            human_approved=True,
            automatic_execution=False,
        )
        self._playbooks[playbook.id] = playbook
        return playbook

    def list_all(self) -> list[StrategyPlaybook]:
        return sorted(self._playbooks.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, playbook_id: UUID) -> StrategyPlaybook | None:
        return self._playbooks.get(playbook_id)

    @staticmethod
    def _normalize(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip().lower() for value in values if value.strip()))

    @staticmethod
    def _readiness_score(payload: PlaybookCreate) -> int:
        score = 20
        score += min(int(payload.win_rate_pct * 0.4), 30)
        if payload.average_r is not None:
            score += 20 if payload.average_r >= 1 else 10 if payload.average_r > 0 else 0
        if payload.profit_factor is not None:
            score += 20 if payload.profit_factor >= 1.5 else 10 if payload.profit_factor >= 1 else 0
        score += min(len(payload.best_setups) * 3, 10)
        score -= min(len(payload.recurring_mistakes) * 8, 40)
        return max(0, min(score, 100))

    def _actions(self, payload: PlaybookCreate) -> list[CoachAction]:
        actions: list[CoachAction] = []
        if payload.win_rate_pct < 45:
            actions.append(CoachAction(priority=CoachPriority.HIGH, category="selection", instruction="Reduce frequency and replay only A-grade setups."))
        if payload.average_r is None or payload.average_r <= 0:
            actions.append(CoachAction(priority=CoachPriority.CRITICAL, category="expectancy", instruction="Keep the strategy in simulation until average R is positive."))
        elif payload.average_r < 1:
            actions.append(CoachAction(priority=CoachPriority.HIGH, category="risk-reward", instruction="Improve exits or reject setups below the target reward-to-risk ratio."))
        if payload.profit_factor is None or payload.profit_factor < 1:
            actions.append(CoachAction(priority=CoachPriority.CRITICAL, category="profit-factor", instruction="Do not approve live use while profit factor is below 1.0."))
        for mistake in self._normalize(payload.recurring_mistakes)[:5]:
            actions.append(CoachAction(priority=CoachPriority.HIGH, category="discipline", instruction=f"Create a hard pre-trade rejection rule for '{mistake}'."))
        if not actions:
            actions.append(CoachAction(priority=CoachPriority.LOW, category="validation", instruction="Continue replay validation and preserve current rules without automatic execution."))
        return actions


strategy_coach_service = StrategyCoachService()
