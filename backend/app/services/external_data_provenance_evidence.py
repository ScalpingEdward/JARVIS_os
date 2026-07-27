from __future__ import annotations

from hashlib import sha256
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.external_data_provenance_evidence import (
    ExternalEvidenceAction,
    ExternalEvidenceCreate,
    ExternalEvidenceDisposition,
    ExternalEvidenceRecord,
    ExternalEvidenceScores,
    ProvenanceState,
)


class ExternalDataProvenanceEvidenceService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], ExternalEvidenceRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "external-data-provenance-freshness-evidence-governance",
            "version": "21.122",
            "provenance_binding_enabled": True,
            "freshness_scoring_enabled": True,
            "evidence_hashing_enabled": True,
            "raw_response_forwarding_enabled": False,
            "external_write_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: ExternalEvidenceCreate) -> ExternalEvidenceRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        bundle_material = "|".join(
            sorted(f"{o.response_id}:{o.source_identity}:{o.evidence_hash}:{o.payload_digest}" for o in payload.observations)
        )
        bundle_digest = sha256(bundle_material.encode()).hexdigest()

        state = ProvenanceState.BLOCKED if "risk-brain-hard-block" in flags else ProvenanceState.EVIDENCE_READY
        record = ExternalEvidenceRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            scores=scores,
            dispositions=dispositions,
            risk_flags=flags,
            evidence_bundle_digest=bundle_digest,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._sources.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[ExternalEvidenceRecord]:
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> ExternalEvidenceRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, record_id: str, payload: ExternalEvidenceAction) -> ExternalEvidenceRecord:
        op = (payload.workspace_id, payload.operation_id)
        if op in self._operations:
            raise ValueError("operation replay detected")

        record = self.get(payload.workspace_id, record_id)
        transitions = {
            "submit-review": ProvenanceState.REVIEW_REQUIRED,
            "approve": ProvenanceState.APPROVED,
            "activate": ProvenanceState.ACTIVE,
            "revoke": ProvenanceState.REVOKED,
            "archive": ProvenanceState.ARCHIVED,
        }
        if payload.action not in transitions:
            raise ValueError("unsupported action")
        if payload.action == "approve" and record.risk_flags:
            raise ValueError("unresolved provenance findings block approval")
        if payload.action == "activate" and record.state != ProvenanceState.APPROVED:
            raise ValueError("human approval required before activation")

        updated = record.model_copy(update={
            "state": transitions[payload.action],
            "approved_by": payload.actor if payload.action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._records[(payload.workspace_id, record_id)] = updated
        self._operations.add(op)
        self._audit_event(updated, payload.action, payload.actor, payload.operation_id, payload.reason)
        return updated

    def audit(self, workspace_id: str) -> List[dict]:
        return [event for event in self._audit if event["workspace_id"] == workspace_id]

    def _assess(self, payload: ExternalEvidenceCreate):
        identity_scores, integrity_scores, freshness_scores, confidence_scores = [], [], [], []
        dispositions: List[ExternalEvidenceDisposition] = []
        flags: List[str] = []

        for o in payload.observations:
            identity = 1.0 if o.source_identity and o.source_uri and o.connector_id else 0.0
            integrity = mean([1.0 if o.evidence_hash else 0.0, 1.0 if o.payload_digest else 0.0, 1.0 if o.schema_validation_passed else 0.0, 1.0 if o.sanitization_passed else 0.0])
            confidence = self._clamp(mean([o.confidence, o.source_reliability, min(1.0, 0.7 + 0.1 * o.corroboration_count)]))
            freshness = self._clamp(o.freshness)
            assurance = self._clamp(mean([identity, integrity, confidence, freshness]))

            identity_scores.append(identity)
            integrity_scores.append(integrity)
            freshness_scores.append(freshness)
            confidence_scores.append(confidence)

            actions: List[str] = []
            signal = "active"
            if payload.require_accepted_response and not o.accepted_response:
                signal = "evidence-gap"
                actions.append("accepted-response-required")
                flags.append(f"unaccepted-response:{o.response_id}")
            if not o.schema_validation_passed or not o.sanitization_passed:
                signal = "evidence-gap"
                actions.append("response-validation-review")
                flags.append(f"validation-gap:{o.response_id}")
            if o.freshness < payload.min_freshness:
                signal = "stale"
                actions.append("refresh-source-evidence")
                flags.append(f"stale-evidence:{o.response_id}")
            if o.confidence < payload.min_confidence or o.source_reliability < payload.min_source_reliability:
                signal = "low-confidence"
                actions.append("corroborate-source")
                flags.append(f"low-confidence:{o.response_id}")
            if payload.criticality >= 0.9 and (not o.accepted_response or not o.schema_validation_passed or freshness < 0.3 or confidence < 0.4):
                signal = "evidence-gap"
                actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")

            dispositions.append(ExternalEvidenceDisposition(
                response_id=o.response_id,
                connector_id=o.connector_id,
                provenance_assurance=assurance,
                evidence_confidence=confidence,
                freshness_score=freshness,
                lifecycle_signal=signal,
                required_actions=sorted(set(actions)),
            ))

        scores = ExternalEvidenceScores(
            identity_assurance=self._clamp(mean(identity_scores)),
            integrity_assurance=self._clamp(mean(integrity_scores)),
            freshness_assurance=self._clamp(mean(freshness_scores)),
            confidence_assurance=self._clamp(mean(confidence_scores)),
            aggregate_assurance=self._clamp(mean(identity_scores + integrity_scores + freshness_scores + confidence_scores)),
        )
        return scores, dispositions, sorted(set(flags))

    def _audit_event(self, record: ExternalEvidenceRecord, action: str, actor: str, operation_id: str, detail: str | None = None) -> None:
        raw = f"{record.workspace_id}|{record.record_id}|{record.evidence_bundle_digest}|{action}|{actor}|{operation_id}|{record.version}"
        self._audit.append({
            "workspace_id": record.workspace_id,
            "record_id": record.record_id,
            "action": action,
            "actor": actor,
            "operation_id": operation_id,
            "detail": detail,
            "event_digest": sha256(raw.encode()).hexdigest(),
        })


external_data_provenance_evidence_service = ExternalDataProvenanceEvidenceService()
