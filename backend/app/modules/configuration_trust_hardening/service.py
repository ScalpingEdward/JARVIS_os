from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from .models import (
    AuditEvent,
    RiskDecision,
    TrustActionRequest,
    TrustAssessment,
    TrustAssessmentCreate,
    TrustBand,
    TrustState,
)


class ConfigurationTrustHardeningError(ValueError):
    pass


class ConfigurationTrustHardeningService:
    def __init__(self) -> None:
        self._records: dict[str, TrustAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipts: set[str] = set()
        self._audit: list[AuditEvent] = []

    def status(self) -> dict[str, object]:
        return {"module": "configuration-trust-hardening", "version": "21.32", "status": "ready"}

    def create(self, payload: TrustAssessmentCreate) -> TrustAssessment:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_keys:
            raise ConfigurationTrustHardeningError("duplicate source_key for workspace")
        state = TrustState.DRAFT
        if payload.risk_decision == RiskDecision.BLOCK:
            state = TrustState.BLOCKED
        elif not payload.provenance_evidence_refs or not payload.runtime_evidence_refs:
            state = TrustState.EVIDENCE_REQUIRED
        record = TrustAssessment(**payload.model_dump(), state=state)
        self._records[record.record_id] = record
        self._source_keys.add(source)
        self._emit(record, "create", "system", None, state)
        return deepcopy(record)

    def list(self, workspace_id: str) -> list[TrustAssessment]:
        return [deepcopy(item) for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> TrustAssessment:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise ConfigurationTrustHardeningError("assessment not found")
        return deepcopy(record)

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [deepcopy(item) for item in self._audit if item.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: TrustActionRequest) -> TrustAssessment:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise ConfigurationTrustHardeningError("assessment not found")
        if record.risk_decision == RiskDecision.BLOCK and request.action != "archive":
            raise ConfigurationTrustHardeningError("Risk Brain hard block is authoritative")

        before = record.state
        transitions = {
            "score": ({TrustState.DRAFT}, TrustState.SCORED),
            "request-review": ({TrustState.SCORED}, TrustState.HUMAN_REVIEW_REQUIRED),
            "approve": ({TrustState.HUMAN_REVIEW_REQUIRED}, TrustState.APPROVED),
            "queue-hardening": ({TrustState.APPROVED}, TrustState.HARDENING_QUEUED),
            "apply-hardening": ({TrustState.HARDENING_QUEUED}, TrustState.HARDENING_APPLIED),
            "verify": ({TrustState.HARDENING_APPLIED}, TrustState.VERIFIED),
            "reject": ({TrustState.HUMAN_REVIEW_REQUIRED, TrustState.APPROVED}, TrustState.REJECTED),
            "fail": ({TrustState.HARDENING_QUEUED, TrustState.HARDENING_APPLIED}, TrustState.FAILED),
            "archive": ({TrustState.VERIFIED, TrustState.REJECTED, TrustState.FAILED, TrustState.BLOCKED}, TrustState.ARCHIVED),
        }
        allowed, target = transitions[request.action]
        if before not in allowed:
            raise ConfigurationTrustHardeningError(f"invalid state transition from {before.value}")

        if request.action == "score":
            node_score = sum(1.0 if n.verified else 0.35 for n in record.nodes) / len(record.nodes)
            edge_score = sum(e.confidence for e in record.edges) / len(record.edges) if record.edges else node_score
            record.trust_score = round((node_score * 0.7 + edge_score * 0.3) * 100, 2)
            record.unverified_node_count = sum(not n.verified for n in record.nodes)
            if record.trust_score >= 90 and record.unverified_node_count == 0:
                record.trust_band = TrustBand.VERIFIED
            elif record.trust_score >= 75:
                record.trust_band = TrustBand.TRUSTED
            elif record.trust_score >= 55:
                record.trust_band = TrustBand.CONDITIONAL
            elif record.trust_score >= 35:
                record.trust_band = TrustBand.DEGRADED
            else:
                record.trust_band = TrustBand.UNTRUSTED
        elif request.action == "approve":
            if not request.approval_token or request.approval_token in self._approval_tokens:
                raise ConfigurationTrustHardeningError("unique approval_token required")
            self._approval_tokens.add(request.approval_token)
            record.approval_actor = request.actor
        elif request.action in {"queue-hardening", "apply-hardening"}:
            if not request.receipt_id or request.receipt_id in self._receipts:
                raise ConfigurationTrustHardeningError("unique receipt_id required")
            self._receipts.add(request.receipt_id)
            record.hardening_receipt_id = request.receipt_id
            if request.action == "apply-hardening":
                expected = {item.control_id for item in record.controls}
                applied = set(request.applied_control_ids)
                if expected != applied:
                    raise ConfigurationTrustHardeningError("all hardening controls must be applied exactly once")
                record.applied_control_ids = request.applied_control_ids
        elif request.action == "verify":
            if not request.receipt_id or request.receipt_id in self._receipts:
                raise ConfigurationTrustHardeningError("unique verification receipt_id required")
            if not request.verification_evidence_refs:
                raise ConfigurationTrustHardeningError("verification evidence is required")
            self._receipts.add(request.receipt_id)
            record.verification_evidence_refs = request.verification_evidence_refs

        record.state = target
        record.updated_at = datetime.now(timezone.utc)
        self._emit(record, request.action, request.actor, before, target)
        return deepcopy(record)

    def _emit(self, record: TrustAssessment, action: str, actor: str, before: TrustState | None, target: TrustState) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=target))


service = ConfigurationTrustHardeningService()
