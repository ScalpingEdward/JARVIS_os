from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.core.auron_integration_readiness_v21_579 import get_integration_readiness


class CrossVerticalCertificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerticalBoundaryEvidence:
    vertical: str
    command_centre_present: bool
    persistent_state: bool
    policy_boundary_present: bool
    simulation_present: bool
    execution_boundary_present: bool
    reconciliation_present: bool
    kill_or_disable_control_present: bool
    command_field_present: bool
    recorded_commands_execute_directly: bool
    live_transport_enabled_by_default: bool


@dataclass(frozen=True)
class CrossVerticalCertificationDecision:
    certified: bool
    verticals: tuple[str, ...]
    blockers: tuple[str, ...]
    live_transports_enabled: bool
    cross_vertical_direct_provider_bypass_allowed: bool


class CrossVerticalIntegrationCertification:
    """E1 architecture-level certification across all governed verticals.

    Certification is evidence-driven and fail-closed. It confirms that each vertical
    exposes the same minimum governance primitives while ensuring no live transport or
    direct provider bypass is enabled by E1.
    """

    REQUIRED_VERTICALS = (
        'trading',
        'instagram-content',
        'communications',
        'research',
        'automation',
        'files-documents',
    )

    def certify(self, evidence: Mapping[str, VerticalBoundaryEvidence]) -> CrossVerticalCertificationDecision:
        blockers: list[str] = []
        for vertical in self.REQUIRED_VERTICALS:
            item = evidence.get(vertical)
            if item is None:
                blockers.append(f'missing-vertical-evidence:{vertical}')
                continue
            if item.vertical != vertical:
                blockers.append(f'vertical-identity-mismatch:{vertical}')
            required_flags = {
                'command-centre': item.command_centre_present,
                'persistent-state': item.persistent_state,
                'policy-boundary': item.policy_boundary_present,
                'simulation': item.simulation_present,
                'execution-boundary': item.execution_boundary_present,
                'reconciliation': item.reconciliation_present,
                'kill-disable-control': item.kill_or_disable_control_present,
                'command-field': item.command_field_present,
            }
            for gate, ok in required_flags.items():
                if not ok:
                    blockers.append(f'{vertical}:{gate}-missing')
            if item.recorded_commands_execute_directly:
                blockers.append(f'{vertical}:recorded-command-direct-execution-forbidden')
            if item.live_transport_enabled_by_default:
                blockers.append(f'{vertical}:live-transport-default-on-forbidden')

        unexpected = sorted(set(evidence).difference(self.REQUIRED_VERTICALS))
        if unexpected:
            blockers.append('unexpected-vertical-evidence:' + ','.join(unexpected))

        readiness = get_integration_readiness()
        architecture_markers = (
            ('trading', 'Trading'),
            ('instagram-content', 'Instagram'),
            ('communications', 'communications'),
            ('research', 'research'),
            ('automation', 'automation'),
            ('files-documents', 'documents'),
        )
        gate_blob = ' '.join(str(x).lower() for x in readiness.get('completed_gates', ()))
        for vertical, marker in architecture_markers:
            if marker.lower() not in gate_blob:
                blockers.append(f'{vertical}:readiness-lineage-not-found')

        return CrossVerticalCertificationDecision(
            certified=not blockers,
            verticals=self.REQUIRED_VERTICALS,
            blockers=tuple(dict.fromkeys(blockers)),
            live_transports_enabled=False,
            cross_vertical_direct_provider_bypass_allowed=False,
        )

    def require_certified(self, evidence: Mapping[str, VerticalBoundaryEvidence]) -> CrossVerticalCertificationDecision:
        decision = self.certify(evidence)
        if not decision.certified:
            raise CrossVerticalCertificationError('cross-vertical integration certification failed: ' + ';'.join(decision.blockers))
        return decision
