from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class ProviderCanaryEvidence:
    vertical: str
    provider_id: str
    certified: bool
    health_certified: bool
    side_effect_free: bool
    provider_write_enabled: bool
    live_execution_enabled: bool
    production_transport_enabled: bool
    risk_score: int


@dataclass(frozen=True)
class ProviderExpansionDecision:
    decision_id: str
    outcome: str
    selected_vertical: str | None
    selected_provider_id: str | None
    selected_scope: str | None
    blockers: tuple[str, ...]
    rationale: tuple[str, ...]
    live_transports_enabled: bool
    trading_live_execution_enabled: bool
    unrestricted_provider_writes_enabled: bool


class ProviderExpansionPromotionPolicyV21_608:
    """G21 promotes an integration-design scope, never a live provider capability.

    The only positive outcome authorizes design/integration work for one external read-only
    sandbox boundary. It does not activate network transport, provider writes, production
    transport or live Trading.
    """

    REQUIRED_VERTICALS = ('research','instagram-content','files-documents','communications','trading')

    @staticmethod
    def _decision_id(payload: dict) -> str:
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return 'provider-expansion-'+digest[:24]

    def evaluate(self, evidence: Iterable[ProviderCanaryEvidence]) -> ProviderExpansionDecision:
        records=tuple(sorted(tuple(evidence),key=lambda e:(e.vertical,e.provider_id)))
        blockers=[]
        if not records:
            blockers.append('provider-canary-evidence-missing')

        verticals=[e.vertical for e in records]
        if len(verticals) != len(set(verticals)):
            blockers.append('duplicate-vertical-evidence')

        required=set(self.REQUIRED_VERTICALS)
        if set(verticals) != required:
            blockers.append('required-canary-evidence-incomplete')

        if any(not e.provider_id.strip() for e in records):
            blockers.append('provider-identity-missing')
        if any(e.risk_score < 0 or e.risk_score > 100 for e in records):
            blockers.append('invalid-risk-score')
        if any(e.live_execution_enabled or e.production_transport_enabled or e.provider_write_enabled for e in records):
            blockers.append('unsafe-provider-capability-detected')
        if any(not e.certified or not e.health_certified for e in records):
            blockers.append('canary-or-health-certification-incomplete')

        selected=None
        if not blockers:
            eligible=[e for e in records if e.side_effect_free and not e.provider_write_enabled
                      and not e.live_execution_enabled and not e.production_transport_enabled]
            # Research is deliberately the first network-facing design target: read-only and
            # non-consequential. Trading remains shadow-only even when its shadow evidence is green.
            research=[e for e in eligible if e.vertical=='research']
            selected=research[0] if research else None
            if selected is None:
                blockers.append('research-readonly-expansion-candidate-unavailable')

        outcome='promote-readonly-sandbox-design' if selected is not None and not blockers else 'hold'
        scope='external-readonly-sandbox-contract-design-only' if selected is not None and not blockers else None
        rationale=(
            'all-provider-specific-canary-and-health-evidence-certified',
            'promotion-applies-to-design-scope-not-live-capability',
            'research-selected-as-first-low-risk-readonly-network-facing-target',
            'network-transport-remains-disabled-until-separate-authorization',
            'provider-writes-and-production-transport-remain-disabled',
            'trading-remains-shadow-only-and-live-execution-ineligible',
        ) if outcome.startswith('promote') else ('expansion-held-until-complete-safe-evidence',)

        payload={
            'records':[asdict(e) for e in records],
            'blockers':blockers,
            'selected':None if selected is None else asdict(selected),
            'outcome':outcome,
            'scope':scope,
        }
        return ProviderExpansionDecision(
            self._decision_id(payload),outcome,
            None if selected is None else selected.vertical,
            None if selected is None else selected.provider_id,
            scope,tuple(blockers),rationale,False,False,False)

    @staticmethod
    def require_promoted(decision: ProviderExpansionDecision) -> ProviderExpansionDecision:
        if decision.outcome != 'promote-readonly-sandbox-design':
            raise RuntimeError('provider expansion promotion not authorized: '+';'.join(decision.blockers))
        if decision.live_transports_enabled or decision.trading_live_execution_enabled or decision.unrestricted_provider_writes_enabled:
            raise RuntimeError('promotion decision attempted to enable forbidden live capability')
        return decision
