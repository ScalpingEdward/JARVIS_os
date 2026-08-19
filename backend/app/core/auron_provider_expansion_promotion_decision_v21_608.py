from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
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
    selected_scope: str | None
    blockers: tuple[str, ...]
    rationale: tuple[str, ...]
    live_transports_enabled: bool
    trading_live_execution_enabled: bool
    unrestricted_provider_writes_enabled: bool


class ProviderExpansionPromotionPolicyV21_608:
    """G21 promotes only the next *integration scope*, never live execution itself.

    A passing decision may authorize work on one low-risk external read-only sandbox contract.
    It cannot enable production transport, provider writes, or live Trading.
    """

    PRIORITY = ('research','files-documents','instagram-content','communications','trading')

    @staticmethod
    def _decision_id(payload: dict) -> str:
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return 'provider-expansion-'+digest[:24]

    def evaluate(self, evidence: Iterable[ProviderCanaryEvidence]) -> ProviderExpansionDecision:
        records=tuple(evidence)
        blockers=[]
        if not records:
            blockers.append('provider-canary-evidence-missing')

        unsafe=[e for e in records if e.live_execution_enabled or e.production_transport_enabled or e.provider_write_enabled]
        if unsafe:
            blockers.append('unsafe-provider-capability-detected')

        required={'research','instagram-content','files-documents','communications','trading'}
        present={e.vertical for e in records}
        missing=sorted(required-present)
        if missing:
            blockers.append('required-canary-evidence-incomplete')

        failed=[e.vertical for e in records if not e.certified or not e.health_certified]
        if failed:
            blockers.append('canary-or-health-certification-incomplete')

        selected=None
        if not blockers:
            eligible=[e for e in records if e.side_effect_free and not e.provider_write_enabled and not e.live_execution_enabled and not e.production_transport_enabled]
            rank={name:i for i,name in enumerate(self.PRIORITY)}
            eligible.sort(key=lambda e:(e.risk_score,rank.get(e.vertical,999),e.vertical,e.provider_id))
            if eligible:
                # Research is the preferred first network-facing expansion because the next phase is read-only sandbox design.
                research=[e for e in eligible if e.vertical=='research']
                selected=research[0] if research else eligible[0]
            else:
                blockers.append('no-side-effect-free-expansion-candidate')

        outcome='promote-readonly-sandbox-design' if selected and not blockers else 'hold'
        scope='external-readonly-sandbox-contract-design-only' if selected else None
        rationale=(
            'all-provider-specific-canary-paths-certified',
            'promotion-applies-to-integration-scope-not-live-capability',
            'research-selected-as-low-risk-readonly-expansion-target',
            'network-and-production-transport-remain-disabled-until-separate-gates',
            'live-trading-remains-explicitly-ineligible',
        ) if selected else ('expansion-held-until-complete-safe-evidence',)
        payload={'records':[e.__dict__ for e in records],'blockers':blockers,'selected':None if selected is None else selected.__dict__,'outcome':outcome,'scope':scope}
        return ProviderExpansionDecision(
            self._decision_id(payload),outcome,None if selected is None else selected.vertical,scope,
            tuple(blockers),rationale,False,False,False)

    @staticmethod
    def require_promoted(decision: ProviderExpansionDecision) -> ProviderExpansionDecision:
        if decision.outcome != 'promote-readonly-sandbox-design':
            raise RuntimeError('provider expansion promotion not authorized: '+';'.join(decision.blockers))
        if decision.live_transports_enabled or decision.trading_live_execution_enabled or decision.unrestricted_provider_writes_enabled:
            raise RuntimeError('promotion decision attempted to enable forbidden live capability')
        return decision
