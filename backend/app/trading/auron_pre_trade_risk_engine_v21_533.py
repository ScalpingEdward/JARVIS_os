from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.trading.auron_strategy_signal_intake_v21_532 import SignalRecord, StrategySignalIntake
from app.trading.auron_trading_account_state_v21_531 import TradingAccountStateStore
from app.trading.auron_trading_registry_v21_530 import TradingAccountRegistry

RiskDecisionState = Literal['approved-for-allocation', 'blocked']


@dataclass(frozen=True)
class RiskPolicy:
    max_risk_per_trade_pct: float = 0.5
    daily_drawdown_buffer_pct: float = 0.25
    max_drawdown_buffer_pct: float = 0.50
    require_complete_prop_limits: bool = True


@dataclass(frozen=True)
class AccountRiskDecision:
    signal_id: str
    account_id: str
    state: RiskDecisionState
    requested_risk_pct: float
    permitted_risk_pct: float
    permitted_risk_amount: float
    daily_drawdown_used_pct: float
    daily_drawdown_headroom_pct: float | None
    max_drawdown_used_pct: float
    max_drawdown_headroom_pct: float | None
    blockers: tuple[str, ...]
    external_calls_made: int = 0


class PreTradeRiskError(RuntimeError):
    pass


class PreTradeRiskEngine:
    """Account-specific, fail-closed pre-trade risk decision layer.

    B4 determines whether a validated strategy signal may progress to allocation
    for each registered account and calculates the maximum permitted monetary
    risk. It deliberately does NOT calculate lots and does NOT place orders.
    """

    def __init__(
        self,
        registry: TradingAccountRegistry,
        states: TradingAccountStateStore,
        signals: StrategySignalIntake,
        policy: RiskPolicy | None = None,
    ) -> None:
        self.registry = registry
        self.states = states
        self.signals = signals
        self.policy = policy or RiskPolicy()
        if not (0 < self.policy.max_risk_per_trade_pct <= 10):
            raise PreTradeRiskError('max_risk_per_trade_pct must be > 0 and <= 10')
        if self.policy.daily_drawdown_buffer_pct < 0 or self.policy.max_drawdown_buffer_pct < 0:
            raise PreTradeRiskError('drawdown buffers cannot be negative')

    @staticmethod
    def _pct_loss(reference: float, value: float) -> float:
        if reference <= 0:
            return 100.0
        return max(0.0, (reference - value) / reference * 100.0)

    def evaluate(self, signal_id: str, account_id: str) -> AccountRiskDecision:
        record = self.signals.get(signal_id)
        if record is None:
            raise KeyError('signal not found')
        account = self.registry.get_account(account_id)
        if account is None:
            raise KeyError('account not found')

        blockers: list[str] = []
        if record.state != 'validated':
            blockers.append('signal-not-validated')
        if record.execution_state not in {'not-dispatched', 'pending-risk-evaluation'}:
            blockers.append('signal-not-eligible-for-risk-evaluation')
        if account.status != 'active':
            blockers.append('account-not-active')

        state = self.states.get_snapshot(account_id)
        if state is None:
            blockers.append('normalized-account-state-missing')

        profile = self.registry.get_rule_profile(account.provider, account.rule_profile_name)
        if profile is None:
            blockers.append('rule-profile-missing')

        requested_risk_pct = record.signal.risk_pct or self.policy.max_risk_per_trade_pct
        requested_risk_pct = min(requested_risk_pct, self.policy.max_risk_per_trade_pct)

        daily_used = 0.0
        max_used = 0.0
        daily_headroom: float | None = None
        max_headroom: float | None = None
        permitted_pct = 0.0
        permitted_amount = 0.0

        if state is not None:
            daily_used = self._pct_loss(state.trading_day.start_balance, state.equity)
            max_used = self._pct_loss(account.initial_balance, state.equity)

        if profile is not None:
            is_prop = account.phase in {'evaluation', 'verification', 'funded'}
            if self.policy.require_complete_prop_limits and is_prop:
                if profile.daily_drawdown_pct is None:
                    blockers.append('daily-drawdown-rule-missing')
                if profile.max_drawdown_pct is None:
                    blockers.append('max-drawdown-rule-missing')

            if profile.daily_drawdown_pct is not None:
                daily_headroom = max(
                    0.0,
                    profile.daily_drawdown_pct - self.policy.daily_drawdown_buffer_pct - daily_used,
                )
                if daily_headroom <= 0:
                    blockers.append('daily-drawdown-headroom-exhausted')

            if profile.max_drawdown_pct is not None:
                max_headroom = max(
                    0.0,
                    profile.max_drawdown_pct - self.policy.max_drawdown_buffer_pct - max_used,
                )
                if max_headroom <= 0:
                    blockers.append('max-drawdown-headroom-exhausted')

        if state is not None and state.equity <= 0:
            blockers.append('non-positive-equity')

        if not blockers and state is not None:
            caps = [requested_risk_pct]
            if daily_headroom is not None:
                caps.append(daily_headroom)
            if max_headroom is not None:
                caps.append(max_headroom)
            permitted_pct = max(0.0, min(caps))
            permitted_amount = state.equity * permitted_pct / 100.0
            if permitted_pct <= 0 or permitted_amount <= 0:
                blockers.append('no-permitted-risk')
                permitted_pct = 0.0
                permitted_amount = 0.0

        decision_state: RiskDecisionState = 'blocked' if blockers else 'approved-for-allocation'
        return AccountRiskDecision(
            signal_id=record.signal.signal_id,
            account_id=account.account_id,
            state=decision_state,
            requested_risk_pct=requested_risk_pct,
            permitted_risk_pct=permitted_pct,
            permitted_risk_amount=permitted_amount,
            daily_drawdown_used_pct=daily_used,
            daily_drawdown_headroom_pct=daily_headroom,
            max_drawdown_used_pct=max_used,
            max_drawdown_headroom_pct=max_headroom,
            blockers=tuple(dict.fromkeys(blockers)),
            external_calls_made=0,
        )

    def evaluate_all_active_accounts(self, signal_id: str) -> tuple[AccountRiskDecision, ...]:
        return tuple(
            self.evaluate(signal_id, account.account_id)
            for account in self.registry.list_accounts()
            if account.status == 'active'
        )

    @staticmethod
    def require_approved(decision: AccountRiskDecision) -> AccountRiskDecision:
        if decision.state != 'approved-for-allocation' or decision.blockers:
            raise PreTradeRiskError(
                f'pre-trade risk blocked for {decision.account_id}: ' + ', '.join(decision.blockers)
            )
        return decision
