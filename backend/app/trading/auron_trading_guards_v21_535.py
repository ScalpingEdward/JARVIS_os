from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from app.trading.auron_multi_account_allocation_v21_534 import AccountChildIntent
from app.trading.auron_trading_account_state_v21_531 import TradingAccountStateStore
from app.trading.auron_trading_registry_v21_530 import TradingAccountRegistry

GuardState = Literal['ready-for-paper-execution', 'blocked']


@dataclass(frozen=True)
class TradingGuardPolicy:
    global_kill_switch: bool = True
    account_kill_switches: dict[str, bool] = field(default_factory=dict)
    allowed_symbols: tuple[str, ...] = ()
    allowed_weekdays_utc: tuple[int, ...] = (0, 1, 2, 3, 4)
    session_start_hour_utc: int = 0
    session_end_hour_utc: int = 24
    max_gross_exposure_pct: float = 5.0
    max_open_positions: int = 10
    max_daily_loss_pct: float = 4.0
    block_during_restricted_news: bool = True


@dataclass(frozen=True)
class GuardContext:
    evaluated_at: datetime
    restricted_news_active: bool = False
    news_reference: str | None = None


@dataclass(frozen=True)
class GuardDecision:
    child_intent_id: str
    account_id: str
    state: GuardState
    blockers: tuple[str, ...]
    gross_exposure_pct: float
    daily_loss_pct: float
    open_positions: int
    external_calls_made: int = 0


class TradingGuardError(RuntimeError):
    pass


class TradingGuardEngine:
    """Final B6 safety gate before any future paper/provider adapter.

    The guard consumes already risk-approved and account-sized child intents. It
    adds operational protections and never places an order itself.
    """

    def __init__(self, registry: TradingAccountRegistry, states: TradingAccountStateStore, policy: TradingGuardPolicy | None = None) -> None:
        self.registry = registry
        self.states = states
        self.policy = policy or TradingGuardPolicy()
        self._validate_policy()

    def _validate_policy(self) -> None:
        p = self.policy
        if not (0 <= p.session_start_hour_utc <= 23 and 1 <= p.session_end_hour_utc <= 24):
            raise TradingGuardError('invalid UTC session hours')
        if p.session_start_hour_utc >= p.session_end_hour_utc:
            raise TradingGuardError('session start must be before session end')
        if p.max_gross_exposure_pct <= 0 or p.max_open_positions < 0 or p.max_daily_loss_pct <= 0:
            raise TradingGuardError('guard limits must be positive')

    @staticmethod
    def _pct_loss(reference: float, value: float) -> float:
        if reference <= 0:
            return 100.0
        return max(0.0, (reference - value) / reference * 100.0)

    def evaluate(self, intent: AccountChildIntent, context: GuardContext | None = None) -> GuardDecision:
        context = context or GuardContext(datetime.now(timezone.utc))
        when = context.evaluated_at.astimezone(timezone.utc)
        blockers: list[str] = []
        p = self.policy

        if intent.state != 'ready-for-guard-evaluation' or intent.blockers:
            blockers.append('child-intent-not-ready')
        account = self.registry.get_account(intent.account_id)
        if account is None:
            blockers.append('account-not-registered')
        elif account.status != 'active':
            blockers.append('account-not-active')
        state = self.states.get_snapshot(intent.account_id)
        if state is None:
            blockers.append('normalized-account-state-missing')

        if p.global_kill_switch:
            blockers.append('global-trading-kill-switch-active')
        if p.account_kill_switches.get(intent.account_id, True):
            blockers.append('account-trading-kill-switch-active')
        if p.allowed_symbols and intent.symbol.upper() not in {s.upper() for s in p.allowed_symbols}:
            blockers.append('symbol-not-allowed')
        if when.weekday() not in p.allowed_weekdays_utc:
            blockers.append('trading-day-not-allowed')
        if not (p.session_start_hour_utc <= when.hour < p.session_end_hour_utc):
            blockers.append('outside-trading-session')
        if p.block_during_restricted_news and context.restricted_news_active:
            blockers.append('restricted-news-window-active')

        gross_exposure_pct = 0.0
        daily_loss_pct = 0.0
        open_positions = 0
        if state is not None:
            open_positions = len(state.positions)
            if state.equity <= 0:
                blockers.append('non-positive-equity')
            else:
                gross_exposure_pct = abs(state.gross_exposure) / state.equity * 100.0
            daily_loss_pct = self._pct_loss(state.trading_day.start_balance, state.equity)
            if gross_exposure_pct >= p.max_gross_exposure_pct:
                blockers.append('gross-exposure-limit-reached')
            if open_positions >= p.max_open_positions:
                blockers.append('open-position-limit-reached')
            if daily_loss_pct >= p.max_daily_loss_pct:
                blockers.append('daily-loss-limit-reached')

        decision_state: GuardState = 'blocked' if blockers else 'ready-for-paper-execution'
        return GuardDecision(
            child_intent_id=intent.child_intent_id,
            account_id=intent.account_id,
            state=decision_state,
            blockers=tuple(dict.fromkeys(blockers)),
            gross_exposure_pct=gross_exposure_pct,
            daily_loss_pct=daily_loss_pct,
            open_positions=open_positions,
            external_calls_made=0,
        )

    @staticmethod
    def require_ready(decision: GuardDecision) -> GuardDecision:
        if decision.state != 'ready-for-paper-execution' or decision.blockers:
            raise TradingGuardError('trading guard blocked: ' + ', '.join(decision.blockers))
        return decision
