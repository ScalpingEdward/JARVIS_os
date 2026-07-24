from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.cybersecurity_privileged_access import (
    CyberAccessDisposition,
    CyberAccessGovernanceCreate,
    CyberAccessGovernanceRecord,
    CyberAccessScores,
    CyberAccessState,
)


@dataclass
class AuditEntry:
    audit_id: str
    workspace_id: str
    record_id: str
    action: str
    actor: str
    operation_id: str
    timestamp: str
    metadata: dict = field(default_factory=dict)


class CybersecurityPrivilegedAccessService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], CyberAccessGovernanceRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "cybersecurity-privileged-access",
            "version": "21.83",
            "governance_only": True,
            "identity_mutation_enabled": False,
            "credential_mutation_enabled": False,
            "network_policy_mutation_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: CyberAccessGovernanceCreate) -> CyberAccessGovernanceRecord:
        identity = (payload.workspace_id, payload.source_key)
        if identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = CyberAccessState.BLOCKED if "risk-brain-hard-block" in flags else CyberAccessState.EVIDENCE_READY
        record = CyberAccessGovernanceRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            scores=scores,
            dispositions=dispositions,
            risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(identity)
        self._append_audit(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[CyberAccessGovernanceRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> CyberAccessGovernanceRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(
        self,
        workspace_id: str,
        record_id: str,
        action: str,
        actor: str,
        operation_id: str,
        reason: str | None = None,
    ) -> CyberAccessGovernanceRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": CyberAccessState.ASSESSED,
            "submit-review": CyberAccessState.REVIEW_REQUIRED,
            "approve": CyberAccessState.APPROVED,
            "activate": CyberAccessState.ACTIVE,
            "monitor": CyberAccessState.MONITORING,
            "suspend": CyberAccessState.SUSPENDED,
            "revoke": CyberAccessState.REVOKED,
            "archive": CyberAccessState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved cybersecurity findings block approval")
        if action == "activate" and record.state != CyberAccessState.APPROVED:
            raise ValueError("human approval required before activation")

        updated = record.model_copy(update={
            "state": transitions[action],
            "approved_by": actor if action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._records[(workspace_id, record_id)] = updated
        self._operation_ids.add(receipt)
        self._append_audit(updated, action, actor, operation_id, {"reason": reason} if reason else {})
        return updated

    def audit(self, workspace_id: str) -> List[AuditEntry]:
        return [entry for entry in self._audit if entry.workspace_id == workspace_id]

    def _assess(self, payload: CyberAccessGovernanceCreate):
        observations = payload.observations
        identity_security = mean((o.identity_assurance + o.mfa_coverage) / 2 for o in observations)
        privilege_security = mean((o.least_privilege_coverage + o.privileged_session_monitoring) / 2 for o in observations)
        credential_security = mean((o.credential_hygiene + o.secret_rotation_coverage) / 2 for o in observations)
        infrastructure_security = mean((o.network_segmentation + o.endpoint_protection + o.patch_compliance) / 3 for o in observations)
        detection_response = mean((o.detection_coverage + o.response_readiness + o.logging_coverage) / 3 for o in observations)
        control_hygiene = mean(1 - min((o.open_critical_findings + o.stale_privileged_accounts) / 20, 1) for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_security = self._clamp(mean([
            identity_security,
            privilege_security,
            credential_security,
            infrastructure_security,
            detection_response,
            control_hygiene,
        ]) * confidence)

        aggregate_residual_risk = self._clamp(mean(
            (1 - o.identity_assurance) * 0.10
            + (1 - o.mfa_coverage) * 0.10
            + (1 - o.least_privilege_coverage) * 0.15
            + (1 - o.privileged_session_monitoring) * 0.10
            + (1 - o.credential_hygiene) * 0.10
            + (1 - o.secret_rotation_coverage) * 0.08
            + (1 - o.network_segmentation) * 0.10
            + (1 - o.detection_coverage) * 0.10
            + (1 - o.response_readiness) * 0.07
            + min(o.open_critical_findings / 10, 1) * 0.05
            + min(o.anomalous_access_events / 20, 1) * 0.05
            for o in observations
        ))

        scores = CyberAccessScores(
            identity_security=self._clamp(identity_security),
            privilege_security=self._clamp(privilege_security),
            credential_security=self._clamp(credential_security),
            infrastructure_security=self._clamp(infrastructure_security),
            detection_response=self._clamp(detection_response),
            control_hygiene=self._clamp(control_hygiene),
            aggregate_security=aggregate_security,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[CyberAccessDisposition] = []
        flags: List[str] = []
        for observation in observations:
            required_actions: List[str] = []
            lifecycle = "secure"
            residual = self._clamp(
                (1 - observation.identity_assurance) * 0.10
                + (1 - observation.mfa_coverage) * 0.10
                + (1 - observation.least_privilege_coverage) * 0.15
                + (1 - observation.privileged_session_monitoring) * 0.10
                + (1 - observation.credential_hygiene) * 0.10
                + (1 - observation.secret_rotation_coverage) * 0.10
                + (1 - observation.network_segmentation) * 0.10
                + (1 - observation.detection_coverage) * 0.10
                + (1 - observation.response_readiness) * 0.05
                + min(observation.open_critical_findings / 10, 1) * 0.05
                + min(observation.anomalous_access_events / 20, 1) * 0.05
            )

            if observation.identity_assurance < 0.75 or observation.mfa_coverage < payload.required_mfa_coverage:
                lifecycle = "identity-alert"
                required_actions.append("identity-assurance-and-mfa-remediation")
                flags.append(f"identity-alert:{observation.control_id}")
            if observation.least_privilege_coverage < payload.required_least_privilege_coverage or observation.stale_privileged_accounts > 0:
                lifecycle = "privilege-alert"
                required_actions.append("privileged-access-review")
                flags.append(f"privilege-alert:{observation.control_id}")
            if observation.credential_hygiene < 0.75 or observation.secret_rotation_coverage < 0.75:
                lifecycle = "credential-alert"
                required_actions.append("credential-and-secret-hygiene-review")
                flags.append(f"credential-alert:{observation.control_id}")
            if observation.network_segmentation < 0.70:
                lifecycle = "segmentation-alert"
                required_actions.append("segmentation-review")
                flags.append(f"segmentation-alert:{observation.control_id}")
            if observation.detection_coverage < payload.required_detection_coverage or observation.logging_coverage < 0.80:
                lifecycle = "detection-gap"
                required_actions.append("detection-and-logging-coverage-review")
                flags.append(f"detection-gap:{observation.control_id}")
            if observation.response_readiness < 0.70:
                lifecycle = "response-gap"
                required_actions.append("incident-response-readiness-review")
                flags.append(f"response-gap:{observation.control_id}")
            if residual > payload.max_acceptable_residual_risk:
                required_actions.append("cyber-risk-committee-escalation")
                flags.append(f"residual-risk-breach:{observation.control_id}")
            if observation.criticality >= 0.90 and (
                observation.open_critical_findings > 0
                or observation.anomalous_access_events >= 5
                or residual >= 0.60
            ):
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")

            dispositions.append(CyberAccessDisposition(
                control_id=observation.control_id,
                domain=observation.domain,
                security_score=self._clamp(1 - residual),
                residual_risk=residual,
                lifecycle_signal=lifecycle,
                required_actions=sorted(set(required_actions)),
            ))

        return scores, dispositions, sorted(set(flags))

    def _append_audit(
        self,
        record: CyberAccessGovernanceRecord,
        action: str,
        actor: str,
        operation_id: str,
        metadata: dict | None = None,
    ) -> None:
        self._audit.append(AuditEntry(
            audit_id=str(uuid4()),
            workspace_id=record.workspace_id,
            record_id=record.record_id,
            action=action,
            actor=actor,
            operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        ))


cybersecurity_privileged_access_service = CybersecurityPrivilegedAccessService()
