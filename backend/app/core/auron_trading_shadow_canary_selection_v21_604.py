from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradingCanaryCandidate:
    provider_id: str
    adapter_id: str
    risk_score: int
    side_effect_free: bool
    broker_network_required: bool
    order_placement_capable: bool
    position_mutation_capable: bool
    allowed_actions: tuple[str, ...]


@dataclass(frozen=True)
class TradingShadowSelectionDecision:
    selected_vertical: str
    provider_id: str
    adapter_id: str
    allowed_actions: tuple[str, ...]
    shadow_only: bool
    live_order_placement_enabled: bool
    broker_network_enabled: bool
    position_mutation_enabled: bool
    production_transport_enabled: bool
    rationale: tuple[str, ...]


class TradingShadowCanarySelectionPolicyV21_604:
    """G17 permits Trading to advance only through a side-effect-free shadow path.

    The selected canary may evaluate plans and simulate order intent locally. It cannot connect
    to a broker, place/cancel/modify orders, mutate positions, or enable production transport.
    """

    def candidates(self) -> tuple[TradingCanaryCandidate, ...]:
        return (
            TradingCanaryCandidate(
                provider_id='trading-analysis-shadow',
                adapter_id='trading-shadow-canary-v1',
                risk_score=55,
                side_effect_free=True,
                broker_network_required=False,
                order_placement_capable=False,
                position_mutation_capable=False,
                allowed_actions=('evaluate-trade-plan','simulate-order-intent'),
            ),
            TradingCanaryCandidate(
                provider_id='trading-live-provider',
                adapter_id='trading-execution-canary-v1',
                risk_score=100,
                side_effect_free=False,
                broker_network_required=True,
                order_placement_capable=True,
                position_mutation_capable=True,
                allowed_actions=('place-order','cancel-order','modify-position'),
            ),
        )

    def select(self) -> TradingShadowSelectionDecision:
        eligible = [
            c for c in self.candidates()
            if c.side_effect_free
            and not c.broker_network_required
            and not c.order_placement_capable
            and not c.position_mutation_capable
        ]
        if not eligible:
            raise RuntimeError('no safe trading shadow canary candidate available')
        selected=min(eligible,key=lambda c:(c.risk_score,c.provider_id))
        return TradingShadowSelectionDecision(
            selected_vertical='trading',
            provider_id=selected.provider_id,
            adapter_id=selected.adapter_id,
            allowed_actions=selected.allowed_actions,
            shadow_only=True,
            live_order_placement_enabled=False,
            broker_network_enabled=False,
            position_mutation_enabled=False,
            production_transport_enabled=False,
            rationale=(
                'research-instagram-documents-communications-provider-canaries-complete',
                'trading-may-advance-only-through-side-effect-free-shadow-analysis',
                'trade-plan-evaluation-and-order-intent-simulation-only',
                'broker-network-and-live-order-placement-remain-ineligible',
                'position-mutation-and-production-transport-remain-disabled',
            ),
        )
