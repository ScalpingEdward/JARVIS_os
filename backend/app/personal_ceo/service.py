from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ExecutiveBriefing,
    ExecutiveBriefingCreate,
    ExecutiveItem,
    ItemState,
    PersonalCEOProfile,
    PersonalCEOStatus,
    RankedExecutiveItem,
    Urgency,
)


class PersonalCEOService:
    def __init__(self) -> None:
        self._profile = PersonalCEOProfile()
        self._briefings: dict[UUID, ExecutiveBriefing] = {}

    def reset(self) -> None:
        self._briefings.clear()
        self._profile = PersonalCEOProfile()

    def profile(self) -> PersonalCEOProfile:
        return self._profile

    def update_profile(self, profile: PersonalCEOProfile) -> PersonalCEOProfile:
        self._profile = profile
        return self._profile

    def create_briefing(self, payload: ExecutiveBriefingCreate) -> ExecutiveBriefing:
        ranked = [self._rank(item) for item in payload.items if item.state != ItemState.completed]
        ranked.sort(key=lambda item: item.priority_score, reverse=True)
        top = ranked[: self._profile.max_daily_priorities]
        deferred_count = max(0, len(ranked) - len(top))

        risks = [
            item.title
            for item in ranked
            if item.state == ItemState.blocked or item.urgency == Urgency.critical
        ][:10]
        approvals = [item.title for item in ranked if item.requires_approval or item.state == ItemState.waiting_approval][:10]
        monitoring = [item.title for item in ranked if item.state == ItemState.monitoring][:10]
        recommendations = [item.next_action for item in top if item.next_action][:10]

        daily_focus = top[0].title if top else "No critical action required"
        headline = (
            f"{len(top)} priorities selected from {len(ranked)} active items."
            if ranked
            else "All tracked areas are clear."
        )
        confidence = round(sum(item.confidence for item in top) / len(top), 4) if top else 1.0

        briefing = ExecutiveBriefing(
            salutation=self._profile.preferred_salutation,
            headline=headline,
            daily_focus=daily_focus,
            top_priorities=top,
            risks=risks,
            approvals=approvals,
            monitoring=monitoring,
            recommendations=recommendations,
            deferred_count=deferred_count,
            confidence=confidence,
        )
        self._briefings[briefing.id] = briefing
        return briefing

    def list_briefings(self) -> list[ExecutiveBriefing]:
        return sorted(self._briefings.values(), key=lambda item: item.generated_at, reverse=True)

    def get(self, briefing_id: UUID) -> ExecutiveBriefing | None:
        return self._briefings.get(briefing_id)

    def latest(self) -> ExecutiveBriefing | None:
        values = self.list_briefings()
        return values[0] if values else None

    def status(self) -> PersonalCEOStatus:
        latest = self.latest()
        return PersonalCEOStatus(
            profile=self._profile,
            briefings=len(self._briefings),
            latest_briefing_at=latest.generated_at if latest else None,
        )

    def _rank(self, item: ExecutiveItem) -> RankedExecutiveItem:
        urgency_weight = {
            Urgency.low: 0.15,
            Urgency.normal: 0.4,
            Urgency.high: 0.72,
            Urgency.critical: 1.0,
        }[item.urgency]
        state_weight = {
            ItemState.ready: 0.6,
            ItemState.blocked: 0.95,
            ItemState.waiting_approval: 0.85,
            ItemState.monitoring: 0.35,
            ItemState.completed: 0.0,
        }[item.state]
        deadline_weight = self._deadline_weight(item.deadline_at)
        approval_weight = 0.15 if item.requires_approval else 0.0
        score = (
            item.impact * 0.34
            + urgency_weight * 0.26
            + state_weight * 0.18
            + deadline_weight * 0.14
            + item.confidence * 0.08
            + approval_weight
        )
        score = round(min(1.0, score), 4)
        reason_parts = [f"impact {item.impact:.2f}", f"urgency {item.urgency.value}", f"state {item.state.value}"]
        if deadline_weight >= 0.8:
            reason_parts.append("deadline imminent")
        if item.requires_approval:
            reason_parts.append("human approval required")
        return RankedExecutiveItem(
            **item.model_dump(),
            priority_score=score,
            priority_reason=", ".join(reason_parts),
        )

    @staticmethod
    def _deadline_weight(deadline_at: datetime | None) -> float:
        if deadline_at is None:
            return 0.2
        now = datetime.now(timezone.utc)
        deadline = deadline_at if deadline_at.tzinfo else deadline_at.replace(tzinfo=timezone.utc)
        hours = (deadline - now).total_seconds() / 3600
        if hours <= 0:
            return 1.0
        if hours <= 6:
            return 0.95
        if hours <= 24:
            return 0.8
        if hours <= 72:
            return 0.55
        return 0.25


personal_ceo_service = PersonalCEOService()
