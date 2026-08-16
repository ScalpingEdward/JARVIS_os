from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from app.trading.auron_controlled_live_enablement_v21_538 import ControlledLiveEnablementService
from app.trading.auron_mt5_broker_adapter_v21_536 import InMemoryReadOnlyBrokerSource, MT5BrokerReadOnlyPaperAdapter
from app.trading.auron_trading_account_state_v21_531 import TradingAccountStateStore
from app.trading.auron_trading_reconciliation_canary_v21_537 import TradingReconciliationCanaryService
from app.trading.auron_trading_registry_v21_530 import TradingAccountRegistry


class TradingCommandCentreService:
    """Read/operate trading safety state without enabling provider writes."""

    def __init__(self, registry: TradingAccountRegistry, states: TradingAccountStateStore,
                 adapter: MT5BrokerReadOnlyPaperAdapter,
                 reconciliation: TradingReconciliationCanaryService,
                 live: ControlledLiveEnablementService) -> None:
        self.registry = registry
        self.states = states
        self.adapter = adapter
        self.reconciliation = reconciliation
        self.live = live

    @staticmethod
    def _pct_loss(reference: float, value: float) -> float:
        if reference <= 0:
            return 100.0
        return max(0.0, (reference - value) / reference * 100.0)

    def account_view(self, account_id: str) -> dict:
        account = self.registry.get_account(account_id)
        if account is None:
            raise KeyError('account not found')
        state = self.states.get_snapshot(account_id)
        profile = self.registry.get_rule_profile(account.provider, account.rule_profile_name)
        scope = self.live.get_scope(account_id)
        canary = self.reconciliation.get_canary_certification(account_id)
        daily_used = self._pct_loss(state.trading_day.start_balance, state.equity) if state else None
        max_used = self._pct_loss(account.initial_balance, state.equity) if state else None
        daily_headroom = None if not profile or profile.daily_drawdown_pct is None or daily_used is None else max(0.0, profile.daily_drawdown_pct - daily_used)
        max_headroom = None if not profile or profile.max_drawdown_pct is None or max_used is None else max(0.0, profile.max_drawdown_pct - max_used)
        alerts: list[str] = []
        if state is None: alerts.append('account-state-missing')
        if profile is None: alerts.append('rule-profile-missing')
        if scope is None: alerts.append('live-scope-missing')
        elif scope.global_kill_switch or scope.account_kill_switch: alerts.append('kill-switch-active')
        if canary is None or canary.state != 'canary-certified': alerts.append('canary-not-certified')
        if daily_headroom is not None and daily_headroom <= 0: alerts.append('daily-dd-exhausted')
        if max_headroom is not None and max_headroom <= 0: alerts.append('max-dd-exhausted')
        return {
            'account': asdict(account),
            'state': asdict(state) if state else None,
            'rule_profile': asdict(profile) if profile else None,
            'daily_drawdown_used_pct': daily_used,
            'daily_drawdown_headroom_pct': daily_headroom,
            'max_drawdown_used_pct': max_used,
            'max_drawdown_headroom_pct': max_headroom,
            'canary': asdict(canary) if canary else None,
            'live_scope': asdict(scope) if scope else None,
            'alerts': alerts,
            'external_calls_made': 0,
        }

    def snapshot(self) -> dict:
        accounts = [self.account_view(a.account_id) for a in self.registry.list_accounts()]
        paper = [asdict(x) for x in self.adapter.list_paper_executions()]
        return {
            'accounts': accounts,
            'paper_executions': paper,
            'provider_write_enabled': False,
            'live_execution_default': False,
            'command_input_available': True,
            'external_calls_made': 0,
        }

    def set_kill_controls(self, account_id: str, *, global_kill_switch: bool,
                          account_kill_switch: bool, actor_approved: bool = False) -> dict:
        account = self.registry.get_account(account_id)
        if account is None:
            raise KeyError('account not found')
        current = self.live.get_scope(account_id)
        scope = self.live.configure_scope(
            account_id,
            account.provider,
            mode=current.mode if current else 'canary',
            operator_approved=current.operator_approved if current else actor_approved,
            global_kill_switch=global_kill_switch,
            account_kill_switch=account_kill_switch,
            enabled=current.enabled if current else False,
        )
        return {'scope': asdict(scope), 'external_calls_made': 0}


def build_default_trading_command_centre() -> TradingCommandCentreService:
    registry = TradingAccountRegistry(Path(os.getenv('AURON_TRADING_REGISTRY_DB', '/tmp/auron_trading_registry.sqlite3')))
    states = TradingAccountStateStore(Path(os.getenv('AURON_TRADING_STATE_DB', '/tmp/auron_trading_state.sqlite3')), registry)
    adapter = MT5BrokerReadOnlyPaperAdapter(Path(os.getenv('AURON_TRADING_PAPER_DB', '/tmp/auron_trading_paper.sqlite3')), registry, states, InMemoryReadOnlyBrokerSource({}))
    reconciliation = TradingReconciliationCanaryService(Path(os.getenv('AURON_TRADING_RECON_DB', '/tmp/auron_trading_recon.sqlite3')), registry, states, adapter)
    live = ControlledLiveEnablementService(Path(os.getenv('AURON_TRADING_LIVE_DB', '/tmp/auron_trading_live.sqlite3')), registry, reconciliation)
    return TradingCommandCentreService(registry, states, adapter, reconciliation, live)
