from __future__ import annotations

from hashlib import sha256
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.evidence_reasoning_context import (
    ConflictFinding,
    ReasoningContextAction,
    ReasoningContextCreate,
    ReasoningContextPacket,
    ReasoningContextState,
)


class EvidenceAwareReasoningContextService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], ReasoningContextPacket] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    def status(self) -> dict:
        return {
            "module": "evidence-aware-reasoning-context-conflict-resolution",
            "version": "21.124",
            "context_assembly_enabled": True,
            "conflict_detection_enabled": True,
            "automatic_external_actions_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: ReasoningContextCreate) -> ReasoningContextPacket:
        source = (payload.workspace_id, payload.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")

        selected = [
            e for e in payload.evidence
            if e.confidence >= payload.min_confidence
            and e.freshness >= payload.min_freshness
            and e.source_reliability >= payload.min_source_reliability
        ]
        if not selected:
            raise ValueError("no evidence satisfies reasoning-context trust thresholds")

        conflicts = self._detect_conflicts(selected)
        flags: List[str] = []
        if conflicts:
            flags.append("evidence-conflict-detected")
        if any(e.criticality >= 0.9 and e.confidence < 0.75 for e in selected):
            flags += ["critical-low-confidence-evidence", "risk-brain-hard-block"]

        confidence = round(mean(e.confidence * e.source_reliability for e in selected), 4)
        freshness = round(mean(e.freshness for e in selected), 4)
        citations = sorted({e.source_citation for e in selected})
        raw = "|".join([
            payload.workspace_id,
            payload.source_key,
            payload.objective,
            *sorted(e.evidence_bundle_digest for e in selected),
        ])
        state = ReasoningContextState.BLOCKED if "risk-brain-hard-block" in flags else (
            ReasoningContextState.CONFLICT if conflicts and payload.require_conflict_resolution else ReasoningContextState.REVIEW_REQUIRED
        )
        record = ReasoningContextPacket(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            objective=payload.objective,
            selected_evidence=selected,
            conflicts=conflicts,
            citations=citations,
            aggregate_confidence=confidence,
            aggregate_freshness=freshness,
            packet_digest=sha256(raw.encode()).hexdigest(),
            risk_flags=sorted(set(flags)),
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._sources.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[ReasoningContextPacket]:
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> ReasoningContextPacket:
        if (workspace_id, record_id) not in self._records:
            raise KeyError("record not found")
        return self._records[(workspace_id, record_id)]

    def act(self, record_id: str, payload: ReasoningContextAction) -> ReasoningContextPacket:
        op = (payload.workspace_id, payload.operation_id)
        if op in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(payload.workspace_id, record_id)

        if payload.action == "resolve-conflicts":
            if not record.conflicts:
                raise ValueError("record has no conflicts")
            updated_conflicts = [c.model_copy(update={"resolution": payload.reason or "human-reviewed"}) for c in record.conflicts]
            updated = record.model_copy(update={
                "conflicts": updated_conflicts,
                "state": ReasoningContextState.REVIEW_REQUIRED,
                "version": record.version + 1,
            })
        elif payload.action == "approve":
            if "risk-brain-hard-block" in record.risk_flags:
                raise ValueError("risk brain hard block prevents approval")
            if any(not c.resolution for c in record.conflicts):
                raise ValueError("all evidence conflicts must be resolved before approval")
            updated = record.model_copy(update={
                "state": ReasoningContextState.APPROVED,
                "approved_by": payload.actor,
                "version": record.version + 1,
            })
        elif payload.action == "mark-ready":
            if record.state != ReasoningContextState.APPROVED:
                raise ValueError("human approval required before ready state")
            updated = record.model_copy(update={"state": ReasoningContextState.READY, "version": record.version + 1})
        elif payload.action == "revoke":
            updated = record.model_copy(update={"state": ReasoningContextState.REVOKED, "version": record.version + 1})
        elif payload.action == "archive":
            updated = record.model_copy(update={"state": ReasoningContextState.ARCHIVED, "version": record.version + 1})
        else:
            raise ValueError("unsupported action")

        self._records[(payload.workspace_id, record_id)] = updated
        self._operations.add(op)
        self._audit_event(updated, payload.action, payload.actor, payload.operation_id, payload.reason)
        return updated

    def audit(self, workspace_id: str) -> List[dict]:
        return [event for event in self._audit if event["workspace_id"] == workspace_id]

    @staticmethod
    def _detect_conflicts(evidence) -> List[ConflictFinding]:
        grouped: Dict[str, List] = {}
        for item in evidence:
            grouped.setdefault(item.claim_key, []).append(item)
        findings: List[ConflictFinding] = []
        for claim_key, items in grouped.items():
            values = sorted({i.claim_value.strip() for i in items})
            if len(values) > 1:
                severity = "high" if any(i.criticality >= 0.8 for i in items) else "medium"
                findings.append(ConflictFinding(
                    claim_key=claim_key,
                    values=values,
                    evidence_ids=[i.memory_record_id for i in items],
                    severity=severity,
                ))
        return findings

    def _audit_event(self, record: ReasoningContextPacket, action: str, actor: str, operation_id: str, detail: str | None = None) -> None:
        raw = f"{record.workspace_id}|{record.record_id}|{action}|{actor}|{operation_id}|{record.version}"
        self._audit.append({
            "workspace_id": record.workspace_id,
            "record_id": record.record_id,
            "action": action,
            "actor": actor,
            "operation_id": operation_id,
            "detail": detail,
            "event_digest": sha256(raw.encode()).hexdigest(),
        })


evidence_aware_reasoning_context_service = EvidenceAwareReasoningContextService()
