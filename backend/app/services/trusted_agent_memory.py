from __future__ import annotations

from hashlib import sha256
from time import time
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.trusted_agent_memory import (
    TrustedMemoryAction,
    TrustedMemoryCreate,
    TrustedMemoryHit,
    TrustedMemoryRecord,
    TrustedMemoryRetrieve,
    TrustedMemoryState,
)


class TrustedAgentMemoryService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], TrustedMemoryRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    def status(self) -> dict:
        return {
            "module": "trusted-context-ingestion-evidence-aware-agent-memory",
            "version": "21.123",
            "trusted_context_ingestion_enabled": True,
            "evidence_aware_retrieval_enabled": True,
            "raw_external_response_ingestion_enabled": False,
            "network_fetch_enabled": False,
            "external_write_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: TrustedMemoryCreate) -> TrustedMemoryRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")
        flags = self._risk_flags(payload)
        state = TrustedMemoryState.BLOCKED if "risk-brain-hard-block" in flags else TrustedMemoryState.REVIEW_REQUIRED
        record = TrustedMemoryRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            agent_id=payload.agent_id, provenance_record_id=payload.provenance_record_id,
            evidence_bundle_digest=payload.evidence_bundle_digest, source_uri=payload.source_uri,
            citation_label=payload.citation_label, content=payload.content, topics=payload.topics,
            data_domains=payload.data_domains, memory_scope=payload.memory_scope,
            confidence=payload.confidence, source_reliability=payload.source_reliability,
            freshness=payload.freshness, ttl_seconds=payload.ttl_seconds, state=state, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._sources.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[TrustedMemoryRecord]:
        self._refresh_states(workspace_id)
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> TrustedMemoryRecord:
        self._refresh_states(workspace_id)
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, record_id: str, payload: TrustedMemoryAction) -> TrustedMemoryRecord:
        op = (payload.workspace_id, payload.operation_id)
        if op in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(payload.workspace_id, record_id)
        if payload.action == "approve":
            if record.risk_flags:
                raise ValueError("unresolved trusted-memory findings block approval")
            updated = record.model_copy(update={"state": TrustedMemoryState.APPROVED, "approved_by": payload.actor, "version": record.version + 1})
        elif payload.action == "activate":
            if record.state != TrustedMemoryState.APPROVED:
                raise ValueError("human approval required before activation")
            now = int(time())
            updated = record.model_copy(update={"state": TrustedMemoryState.ACTIVE, "activated_at_epoch": now, "expires_at_epoch": now + record.ttl_seconds, "version": record.version + 1})
        elif payload.action == "revoke":
            updated = record.model_copy(update={"state": TrustedMemoryState.REVOKED, "version": record.version + 1})
        elif payload.action == "archive":
            updated = record.model_copy(update={"state": TrustedMemoryState.ARCHIVED, "version": record.version + 1})
        else:
            raise ValueError("unsupported action")
        self._records[(payload.workspace_id, record_id)] = updated
        self._operations.add(op)
        self._audit_event(updated, payload.action, payload.actor, payload.operation_id, payload.reason)
        return updated

    def retrieve(self, request: TrustedMemoryRetrieve) -> List[TrustedMemoryHit]:
        self._refresh_states(request.workspace_id)
        hits: List[TrustedMemoryHit] = []
        for (ws, _), record in self._records.items():
            if ws != request.workspace_id or record.agent_id != request.agent_id or record.state != TrustedMemoryState.ACTIVE:
                continue
            if record.confidence < request.min_confidence or record.freshness < request.min_freshness:
                continue
            if request.topics and not set(request.topics).intersection(record.topics):
                continue
            if request.data_domains and not set(request.data_domains).intersection(record.data_domains):
                continue
            score = round(record.confidence * 0.45 + record.freshness * 0.35 + record.source_reliability * 0.20, 4)
            hits.append(TrustedMemoryHit(
                record_id=record.record_id, citation_label=record.citation_label, source_uri=record.source_uri,
                provenance_record_id=record.provenance_record_id, evidence_bundle_digest=record.evidence_bundle_digest,
                content=record.content, confidence=record.confidence, freshness=record.freshness, score=score,
            ))
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[: request.max_items]

    def audit(self, workspace_id: str) -> List[dict]:
        return [e for e in self._audit if e["workspace_id"] == workspace_id]

    def _risk_flags(self, payload: TrustedMemoryCreate) -> List[str]:
        flags: List[str] = []
        if not payload.evidence_bundle_digest.startswith(("sha256:", "sha512:")):
            flags.append("invalid-evidence-digest")
        if payload.confidence < payload.min_confidence:
            flags.append("low-confidence")
        if payload.source_reliability < payload.min_source_reliability:
            flags.append("low-source-reliability")
        if payload.freshness < payload.min_freshness:
            flags.append("stale-evidence")
        if payload.criticality >= 0.90 and ("invalid-evidence-digest" in flags or payload.confidence < 0.40 or payload.freshness < 0.20):
            flags.append("risk-brain-hard-block")
        return sorted(set(flags))

    def _refresh_states(self, workspace_id: str) -> None:
        now = int(time())
        for key, record in list(self._records.items()):
            if key[0] != workspace_id or record.state != TrustedMemoryState.ACTIVE:
                continue
            if record.expires_at_epoch is not None and now >= record.expires_at_epoch:
                self._records[key] = record.model_copy(update={"state": TrustedMemoryState.EXPIRED, "version": record.version + 1})

    def _audit_event(self, record: TrustedMemoryRecord, action: str, actor: str, operation_id: str, detail: str | None = None) -> None:
        raw = f"{record.workspace_id}|{record.record_id}|{action}|{actor}|{operation_id}|{record.version}"
        self._audit.append({
            "workspace_id": record.workspace_id, "record_id": record.record_id, "action": action,
            "actor": actor, "operation_id": operation_id, "detail": detail,
            "event_digest": sha256(raw.encode()).hexdigest(),
        })


trusted_agent_memory_service = TrustedAgentMemoryService()
