from __future__ import annotations

from copy import deepcopy
from statistics import mean
from typing import Dict, List
from uuid import uuid4

from app.schemas.institutional_compliance import (
    ComplianceAssessment,
    ComplianceState,
    InstitutionalComplianceAction,
    InstitutionalComplianceCreate,
    InstitutionalComplianceRecord,
    InstitutionalComplianceScores,
)


class InstitutionalComplianceService:
    def __init__(self) -> None:
        self._records: Dict[str, InstitutionalComplianceRecord] = {}
        self._source_keys: Dict[str, str] = {}
        self._operations: set[str] = set()
        self._audit: List[dict] = []

    @staticmethod
    def _weighted(value: float, confidence: float, freshness: float) -> float:
        return max(0.0, min(1.0, value * confidence * freshness))

    def create(self, payload: InstitutionalComplianceCreate) -> InstitutionalComplianceRecord:
        source_scope = f"{payload.workspace_id}:{payload.source_key}"
        if source_scope in self._source_keys:
            raise ValueError("duplicate source key")

        assessments: List[ComplianceAssessment] = []
        flags: List[str] = []
        required_actions: List[str] = []

        for item in payload.observations:
            evidence = mean([item.evidence_completeness, item.recordkeeping_quality])
            monitoring = mean([item.surveillance_coverage, item.control_effectiveness])
            raw_compliance = mean(
                [
                    item.policy_coverage,
                    item.control_effectiveness,
                    item.disclosure_readiness,
                    item.surveillance_coverage,
                    item.recordkeeping_quality,
                ]
            )
            compliance = self._weighted(raw_compliance, item.confidence, item.freshness)
            severity = min(
                1.0,
                (1 - compliance) * 0.55
                + min(1.0, item.restriction_breach_count / 3) * 0.25
                + min(1.0, item.unresolved_findings / 5) * 0.20,
            ) * item.materiality

            disposition = "compliant"
            if item.restriction_breach_count:
                disposition = "restriction-alert"
                flags.append(f"restriction-breach:{item.control_id}")
                required_actions.append(f"review-restriction:{item.control_id}")
            elif item.recordkeeping_quality < 0.65:
                disposition = "recordkeeping-alert"
                flags.append(f"recordkeeping-gap:{item.control_id}")
                required_actions.append(f"remediate-recordkeeping:{item.control_id}")
            elif item.surveillance_coverage < 0.65:
                disposition = "surveillance-alert"
                flags.append(f"surveillance-gap:{item.control_id}")
                required_actions.append(f"expand-surveillance:{item.control_id}")
            elif item.disclosure_readiness < 0.65:
                disposition = "disclosure-gap"
                flags.append(f"disclosure-gap:{item.control_id}")
                required_actions.append(f"prepare-disclosure:{item.control_id}")
            elif compliance < 0.75:
                disposition = "control-gap"
                flags.append(f"control-gap:{item.control_id}")
                required_actions.append(f"strengthen-control:{item.control_id}")

            assessments.append(
                ComplianceAssessment(
                    control_id=item.control_id,
                    domain=item.domain,
                    jurisdiction=item.jurisdiction,
                    compliance_score=round(compliance, 4),
                    evidence_score=round(evidence, 4),
                    monitoring_score=round(monitoring, 4),
                    severity_score=round(severity, 4),
                    disposition=disposition,
                )
            )

        domains = {item.domain for item in payload.observations}
        jurisdictions = {item.jurisdiction for item in payload.observations}
        for domain in payload.restricted_domains:
            if domain in domains:
                flags.append(f"restricted-domain-present:{domain}")
                required_actions.append(f"legal-review-domain:{domain}")
        for jurisdiction in payload.required_jurisdictions:
            if jurisdiction not in jurisdictions:
                flags.append(f"jurisdiction-evidence-missing:{jurisdiction}")
                required_actions.append(f"collect-jurisdiction-evidence:{jurisdiction}")

        observations = payload.observations
        restriction_integrity = 1 - min(1.0, sum(o.restriction_breach_count for o in observations) / 3)
        confidence = mean(self._weighted(1.0, o.confidence, o.freshness) for o in observations)
        scores = InstitutionalComplianceScores(
            policy_coverage=round(mean(o.policy_coverage for o in observations), 4),
            evidence_integrity=round(mean(o.evidence_completeness for o in observations), 4),
            control_effectiveness=round(mean(o.control_effectiveness for o in observations), 4),
            disclosure_readiness=round(mean(o.disclosure_readiness for o in observations), 4),
            surveillance_coverage=round(mean(o.surveillance_coverage for o in observations), 4),
            recordkeeping_quality=round(mean(o.recordkeeping_quality for o in observations), 4),
            restriction_integrity=round(restriction_integrity, 4),
            aggregate_compliance=round(mean(a.compliance_score for a in assessments), 4),
            confidence=round(confidence, 4),
        )

        state = ComplianceState.EVIDENCE_READY
        record = InstitutionalComplianceRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            scores=scores,
            assessments=assessments,
            required_actions=sorted(set(required_actions)),
            risk_flags=sorted(set(flags)),
        )
        self._records[record.record_id] = record
        self._source_keys[source_scope] = record.record_id
        self._log(record, payload.requested_by, "create")
        return deepcopy(record)

    def list(self, workspace_id: str) -> List[InstitutionalComplianceRecord]:
        return [deepcopy(r) for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> InstitutionalComplianceRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError("record not found")
        return deepcopy(record)

    def act(self, workspace_id: str, record_id: str, payload: InstitutionalComplianceAction) -> InstitutionalComplianceRecord:
        if payload.operation_id in self._operations:
            raise ValueError("operation replay detected")
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError("record not found")

        transitions = {
            "assess": ComplianceState.ASSESSED,
            "submit-review": ComplianceState.REVIEW_REQUIRED,
            "approve": ComplianceState.APPROVED,
            "activate": ComplianceState.ACTIVE,
            "monitor": ComplianceState.MONITORING,
            "suspend": ComplianceState.SUSPENDED,
            "revoke": ComplianceState.REVOKED,
            "archive": ComplianceState.ARCHIVED,
        }
        if payload.action == "approve" and record.risk_flags:
            raise ValueError("compliance flags require remediation before approval")
        if payload.action == "activate" and not record.approved_by:
            raise ValueError("human approval required")

        record.state = transitions[payload.action]
        if payload.action == "approve":
            record.approved_by = payload.actor
        record.version += 1
        self._operations.add(payload.operation_id)
        self._log(record, payload.actor, payload.action, payload.reason)
        return deepcopy(record)

    def audit(self, workspace_id: str) -> List[dict]:
        return [deepcopy(event) for event in self._audit if event["workspace_id"] == workspace_id]

    def _log(self, record: InstitutionalComplianceRecord, actor: str, action: str, reason: str | None = None) -> None:
        self._audit.append(
            {
                "record_id": record.record_id,
                "workspace_id": record.workspace_id,
                "version": record.version,
                "state": record.state.value,
                "actor": actor,
                "action": action,
                "reason": reason,
            }
        )


institutional_compliance_service = InstitutionalComplianceService()
