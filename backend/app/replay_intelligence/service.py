from collections import Counter
from uuid import UUID

from .models import (
    JournalEntry,
    JournalEntryCreate,
    JournalSummary,
    ReplayIntelligenceStatus,
    TradeDirection,
    TradeOutcome,
)


class ReplayIntelligenceService:
    def __init__(self) -> None:
        self._entries: dict[UUID, JournalEntry] = {}

    def status(self) -> ReplayIntelligenceStatus:
        return ReplayIntelligenceStatus()

    def create(self, payload: JournalEntryCreate) -> JournalEntry:
        movement = payload.exit_price - payload.entry_price
        gross_pnl = movement if payload.direction == TradeDirection.LONG else -movement
        pnl = round(gross_pnl - payload.fees, 8)
        if pnl > 0:
            outcome = TradeOutcome.WIN
        elif pnl < 0:
            outcome = TradeOutcome.LOSS
        else:
            outcome = TradeOutcome.BREAKEVEN
        r_multiple = round(pnl / payload.risk_amount, 4) if payload.risk_amount > 0 else None
        entry = JournalEntry(
            replay_session_id=payload.replay_session_id,
            symbol=payload.symbol.upper(),
            timeframe=payload.timeframe.upper(),
            direction=payload.direction,
            entry_price=payload.entry_price,
            exit_price=payload.exit_price,
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit,
            risk_amount=payload.risk_amount,
            fees=payload.fees,
            pnl=pnl,
            r_multiple=r_multiple,
            outcome=outcome,
            setup_tags=self._normalize_tags(payload.setup_tags),
            mistakes=self._normalize_tags(payload.mistakes),
            notes=payload.notes.strip(),
            human_approved=True,
            automatic_execution=False,
        )
        self._entries[entry.id] = entry
        return entry

    def list_all(self, replay_session_id: UUID | None = None) -> list[JournalEntry]:
        entries = list(self._entries.values())
        if replay_session_id is not None:
            entries = [item for item in entries if item.replay_session_id == replay_session_id]
        return sorted(entries, key=lambda item: item.created_at, reverse=True)

    def get(self, entry_id: UUID) -> JournalEntry | None:
        return self._entries.get(entry_id)

    def summary(self, replay_session_id: UUID | None = None) -> JournalSummary:
        entries = self.list_all(replay_session_id)
        wins = [item for item in entries if item.outcome == TradeOutcome.WIN]
        losses = [item for item in entries if item.outcome == TradeOutcome.LOSS]
        breakeven = [item for item in entries if item.outcome == TradeOutcome.BREAKEVEN]
        gross_profit = round(sum(item.pnl for item in wins), 8)
        gross_loss = round(abs(sum(item.pnl for item in losses)), 8)
        net_pnl = round(sum(item.pnl for item in entries), 8)
        profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else None
        r_values = [item.r_multiple for item in entries if item.r_multiple is not None]
        average_r = round(sum(r_values) / len(r_values), 4) if r_values else None
        setup_counts = Counter(tag for item in wins for tag in item.setup_tags)
        mistake_counts = Counter(tag for item in entries for tag in item.mistakes)
        total = len(entries)
        return JournalSummary(
            total_trades=total,
            wins=len(wins),
            losses=len(losses),
            breakeven=len(breakeven),
            win_rate_pct=round(len(wins) / total * 100, 2) if total else 0,
            net_pnl=net_pnl,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=profit_factor,
            average_r=average_r,
            best_setup_tags=[tag for tag, _ in setup_counts.most_common(5)],
            recurring_mistakes=[tag for tag, _ in mistake_counts.most_common(5)],
            recommendation=self._recommendation(total, len(wins), average_r, mistake_counts),
        )

    @staticmethod
    def _normalize_tags(tags: list[str]) -> list[str]:
        return list(dict.fromkeys(tag.strip().lower() for tag in tags if tag.strip()))

    @staticmethod
    def _recommendation(total: int, wins: int, average_r: float | None, mistakes: Counter) -> str:
        if total < 10:
            return "MASTER Brano: collect at least 10 replay trades before changing the strategy."
        if mistakes:
            mistake, _ = mistakes.most_common(1)[0]
            return f"MASTER Brano: review recurring mistake '{mistake}' before approving live use."
        if average_r is not None and average_r <= 0:
            return "MASTER Brano: replay expectancy is not positive; keep the strategy in simulation."
        win_rate = wins / total * 100
        return f"MASTER Brano: replay evidence shows {win_rate:.1f}% wins; human validation is still required."


replay_intelligence_service = ReplayIntelligenceService()
