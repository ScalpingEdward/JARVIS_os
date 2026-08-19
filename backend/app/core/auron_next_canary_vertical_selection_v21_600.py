from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanaryCandidate:
    vertical: str
    provider_id: str
    adapter_id: str
    utility_score: int
    risk_score: int
    side_effect_free: bool
    write_capable: bool
    external_network_required: bool
    already_certified: bool
    allowed_actions: tuple[str, ...]


@dataclass(frozen=True)
class CanarySelectionDecision:
    selected_vertical: str
    provider_id: str
    adapter_id: str
    allowed_actions: tuple[str, ...]
    rationale: tuple[str, ...]
    production_transport_enabled: bool
    provider_write_enabled: bool
    outbound_message_enabled: bool
    trading_execution_enabled: bool


class NextCanaryVerticalSelectionPolicyV21_600:
    """G13 deterministic selection after Research, Instagram and Documents canary completion."""

    def candidates(self) -> tuple[CanaryCandidate, ...]:
        return (
            CanaryCandidate('research','research-local-readonly','research-readonly-canary-v1',80,10,True,False,False,True,('search-preview','inspect-source-metadata')),
            CanaryCandidate('instagram-content','instagram-local-draft-preview','instagram-draft-preview-canary-v1',90,20,True,False,False,True,('render-draft-preview','inspect-draft-metadata')),
            CanaryCandidate('files-documents','documents-local-readonly','documents-readonly-canary-v1',78,12,True,False,False,True,('inspect-file-metadata','preview-file-version')),
            CanaryCandidate('communications','communications-local-draft','communications-draft-canary-v1',76,25,True,False,False,False,('render-message-preview','inspect-recipient-plan')),
            CanaryCandidate('trading','trading-analysis-shadow','trading-shadow-canary-v1',100,55,True,False,False,False,('evaluate-trade-plan','simulate-order-intent')),
            CanaryCandidate('trading','trading-live-provider','trading-execution-canary-v1',100,100,False,True,True,False,('place-order',)),
        )

    def select(self) -> CanarySelectionDecision:
        eligible=[c for c in self.candidates() if not c.already_certified and c.side_effect_free and not c.write_capable and not c.external_network_required]
        if not eligible:
            raise RuntimeError('no safe next canary candidate available')
        selected=min(eligible,key=lambda c:(c.risk_score,-c.utility_score,c.vertical))
        return CanarySelectionDecision(
            selected_vertical=selected.vertical,
            provider_id=selected.provider_id,
            adapter_id=selected.adapter_id,
            allowed_actions=selected.allowed_actions,
            rationale=(
                'research-instagram-documents-provider-canaries-complete',
                'communications-is-lowest-risk-remaining-side-effect-free-local-candidate',
                'draft-preview-and-recipient-plan-only-before-any-message-send',
                'trading-shadow-remains-deferred-behind-lower-risk-local-communications',
                'live-trading-order-placement-remains-ineligible',
            ),
            production_transport_enabled=False,
            provider_write_enabled=False,
            outbound_message_enabled=False,
            trading_execution_enabled=False,
        )
