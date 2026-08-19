from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanaryVerticalCandidate:
    vertical: str
    provider_id: str
    adapter_id: str
    utility_score: int
    risk_score: int
    side_effect_free: bool
    write_capable: bool
    external_network_required: bool
    allowed_actions: tuple[str, ...]


@dataclass(frozen=True)
class CanaryVerticalSelection:
    selected_vertical: str
    provider_id: str
    adapter_id: str
    allowed_actions: tuple[str, ...]
    rationale: tuple[str, ...]
    production_transport_enabled: bool
    publish_enabled: bool
    trading_execution_enabled: bool


class NextCanaryVerticalSelectionPolicy:
    """G5 deterministic risk/utility selection for the next provider-specific canary.

    Research is already certified. The next increment must increase product utility without
    jumping directly to consequential trading execution or public publishing. Therefore the
    selected Instagram Content canary is constrained to local draft-preview inspection only.
    """

    def candidates(self) -> tuple[CanaryVerticalCandidate, ...]:
        return (
            CanaryVerticalCandidate(
                vertical='instagram-content', provider_id='instagram-local-draft-preview',
                adapter_id='instagram-draft-preview-canary-v1', utility_score=90, risk_score=20,
                side_effect_free=True, write_capable=False, external_network_required=False,
                allowed_actions=('render-draft-preview','inspect-draft-metadata'),
            ),
            CanaryVerticalCandidate(
                vertical='files-documents', provider_id='documents-local-readonly',
                adapter_id='documents-readonly-canary-v1', utility_score=65, risk_score=15,
                side_effect_free=True, write_capable=False, external_network_required=False,
                allowed_actions=('inspect-file-metadata','preview-file-version'),
            ),
            CanaryVerticalCandidate(
                vertical='communications', provider_id='communications-local-draft',
                adapter_id='communications-draft-canary-v1', utility_score=70, risk_score=35,
                side_effect_free=True, write_capable=False, external_network_required=False,
                allowed_actions=('render-message-preview','inspect-recipient-plan'),
            ),
            CanaryVerticalCandidate(
                vertical='trading', provider_id='trading-live-provider',
                adapter_id='trading-execution-canary-v1', utility_score=100, risk_score=100,
                side_effect_free=False, write_capable=True, external_network_required=True,
                allowed_actions=('place-order',),
            ),
        )

    def select(self) -> CanaryVerticalSelection:
        eligible = [c for c in self.candidates()
                    if c.side_effect_free and not c.write_capable and not c.external_network_required]
        if not eligible:
            raise RuntimeError('no safe next canary vertical available')
        selected = max(eligible, key=lambda c: (c.utility_score - c.risk_score, c.utility_score, -c.risk_score))
        return CanaryVerticalSelection(
            selected_vertical=selected.vertical,
            provider_id=selected.provider_id,
            adapter_id=selected.adapter_id,
            allowed_actions=selected.allowed_actions,
            rationale=(
                'highest-risk-adjusted-utility-among-side-effect-free-candidates',
                'local-draft-preview-before-provider-publish',
                'instagram-content-utility-without-public-write',
                'trading-live-execution-deferred-as-high-consequence',
            ),
            production_transport_enabled=False,
            publish_enabled=False,
            trading_execution_enabled=False,
        )
