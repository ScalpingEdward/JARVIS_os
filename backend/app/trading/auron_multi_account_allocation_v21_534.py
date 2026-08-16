from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Literal

from app.trading.auron_pre_trade_risk_engine_v21_533 import AccountRiskDecision, PreTradeRiskEngine
from app.trading.auron_strategy_signal_intake_v21_532 import StrategySignalIntake

ChildIntentState = Literal['ready-for-guard-evaluation', 'blocked']


class AllocationError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstrumentSizingSpec:
    symbol: str
    value_per_price_unit_per_lot: float
    min_lot: float
    max_lot: float
    lot_step: float


@dataclass(frozen=True)
class AccountChildIntent:
    child_intent_id: str
    signal_id: str
    account_id: str
    symbol: str
    side: str
    signal_type: str
    reference_price: float
    stop_loss: float
    take_profit: float | None
    risk_amount: float
    risk_pct: float
    calculated_lot: float
    state: ChildIntentState
    blockers: tuple[str, ...]
    external_calls_made: int = 0


@dataclass(frozen=True)
class AllocationBatch:
    signal_id: str
    child_intents: tuple[AccountChildIntent, ...]
    approved_accounts: tuple[str, ...]
    blocked_accounts: tuple[str, ...]
    external_calls_made: int = 0


class MultiAccountAllocationEngine:
    """Converts one master signal into account-safe child intents.

    B5 never copies a master lot size. Every account is re-sized from its own B4
    permitted monetary risk and the signal stop distance. It does not place orders.
    """

    def __init__(self, signals: StrategySignalIntake, risk_engine: PreTradeRiskEngine) -> None:
        self.signals = signals
        self.risk_engine = risk_engine

    @staticmethod
    def _round_down(value: float, step: float) -> float:
        if step <= 0:
            raise AllocationError('lot_step must be positive')
        units = (Decimal(str(value)) / Decimal(str(step))).to_integral_value(rounding=ROUND_DOWN)
        return float(units * Decimal(str(step)))

    @staticmethod
    def _validate_spec(spec: InstrumentSizingSpec) -> None:
        if not spec.symbol.strip():
            raise AllocationError('sizing symbol is required')
        if spec.value_per_price_unit_per_lot <= 0:
            raise AllocationError('value_per_price_unit_per_lot must be positive')
        if spec.min_lot <= 0 or spec.max_lot <= 0 or spec.lot_step <= 0:
            raise AllocationError('lot constraints must be positive')
        if spec.min_lot > spec.max_lot:
            raise AllocationError('min_lot cannot exceed max_lot')

    def _child_from_decision(
        self,
        *,
        decision: AccountRiskDecision,
        reference_price: float,
        spec: InstrumentSizingSpec,
    ) -> AccountChildIntent:
        record = self.signals.get(decision.signal_id)
        if record is None:
            raise KeyError('signal not found')
        signal = record.signal
        blockers: list[str] = []

        if decision.state != 'approved-for-allocation' or decision.blockers:
            blockers.append('risk-decision-not-approved')
        if signal.symbol.upper() != spec.symbol.upper():
            blockers.append('sizing-spec-symbol-mismatch')
        if reference_price <= 0:
            blockers.append('invalid-reference-price')
        stop_distance = abs(reference_price - signal.stop_loss)
        if stop_distance <= 0:
            blockers.append('zero-stop-distance')

        raw_lot = 0.0
        lot = 0.0
        if not blockers:
            raw_lot = decision.permitted_risk_amount / (stop_distance * spec.value_per_price_unit_per_lot)
            lot = self._round_down(raw_lot, spec.lot_step)
            lot = min(lot, spec.max_lot)
            if lot < spec.min_lot:
                blockers.append('calculated-lot-below-minimum')
                lot = 0.0

        state: ChildIntentState = 'blocked' if blockers else 'ready-for-guard-evaluation'
        return AccountChildIntent(
            child_intent_id=f'{signal.signal_id}:{decision.account_id}',
            signal_id=signal.signal_id,
            account_id=decision.account_id,
            symbol=signal.symbol,
            side=signal.side,
            signal_type=signal.signal_type,
            reference_price=reference_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            risk_amount=decision.permitted_risk_amount if not blockers else 0.0,
            risk_pct=decision.permitted_risk_pct if not blockers else 0.0,
            calculated_lot=lot,
            state=state,
            blockers=tuple(dict.fromkeys(blockers)),
            external_calls_made=0,
        )

    def allocate(
        self,
        signal_id: str,
        *,
        reference_price: float,
        sizing_spec: InstrumentSizingSpec,
    ) -> AllocationBatch:
        self._validate_spec(sizing_spec)
        record = self.signals.get(signal_id)
        if record is None:
            raise KeyError('signal not found')
        if record.state != 'validated':
            raise AllocationError('only validated signals may be allocated')
        if record.execution_state not in {'not-dispatched', 'pending-risk-evaluation'}:
            raise AllocationError('signal is not eligible for allocation')

        decisions = self.risk_engine.evaluate_all_active_accounts(signal_id)
        children = tuple(
            self._child_from_decision(
                decision=decision,
                reference_price=reference_price,
                spec=sizing_spec,
            )
            for decision in decisions
        )
        approved = tuple(c.account_id for c in children if c.state == 'ready-for-guard-evaluation')
        blocked = tuple(c.account_id for c in children if c.state == 'blocked')
        return AllocationBatch(signal_id, children, approved, blocked, 0)

    @staticmethod
    def require_ready(intent: AccountChildIntent) -> AccountChildIntent:
        if intent.state != 'ready-for-guard-evaluation' or intent.blockers:
            raise AllocationError(
                f'child intent blocked for {intent.account_id}: ' + ', '.join(intent.blockers)
            )
        return intent
