from __future__ import annotations

from hashlib import sha256
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.execution_authorization_chain_verification import (
    AuthorizationChainAction,
    AuthorizationChainCreate,
    AuthorizationChainRecord,
    AuthorizationChainScores,
    AuthorizationChainState,
)


class ExecutionAuthorizationChainVerificationService:
    PROTECTED_OPERATIONS = {
        "fund-movement",
        "order-submit",
        "trade-execute",
        "credential-mutate",
        "permission-escalate",
        "safety-control-disable",
    }
    REQUIRED_STAGES = ["decision", "proposal", "binding", "sandbox", "adapter", "gateway", "worker"]
    ACCEPTED_STATES = {
        "decision": {"approved", "ready"},
        "proposal": {"approved", "authorized", "ready"},
        "binding": {"approved", "ready"},
        "sandbox": {"approved", "authorized", "ready"},
        "adapter": {"active", "approved", "ready"},
        "gateway": {"approved", "authorized", "ready", "dispatch-ready"},
        "worker": {"leased", "running", "ready", "active"},
    }

    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AuthorizationChainRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    def status(self) -> dict:
        return {
            "module": "end-to-end-execution-authorization-chain-verification",
            "version": "21.128",
            "verification_enabled": True,
            "controlled_read_only_dispatch_eligibility_enabled": True,
            "dispatch_execution_enabled": False,
            "fund_movement_enabled": False,
            "order_submission_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AuthorizationChainCreate) -> AuthorizationChainRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")

        flags = self._risk_flags(payload)
        scores = self._scores(payload)
        raw = "|".join(
            f"{link.stage}:{link.record_id}:{link.digest}:{link.state}:{link.workspace_id}:{link.operation or ''}:{link.target or ''}"
            for link in sorted(payload.links, key=lambda item: self.REQUIRED_STAGES.index(item.stage) if item.stage in self.REQUIRED_STAGES else 999)
        )
        chain_digest = sha256(raw.encode()).hexdigest()
        state = AuthorizationChainState.BLOCKED if "risk-brain-hard-block" in flags else AuthorizationChainState.REVIEW_REQUIRED
        record = AuthorizationChainRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            expected_operation=payload.expected_operation,
            expected_target=payload.expected_target,
            chain_digest=chain_digest,
            scores=scores,
            risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._sources.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[AuthorizationChainRecord]:
        return [record for (ws, _), record in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AuthorizationChainRecord:
        if (workspace_id, record_id) not in self._records:
            raise KeyError("record not found")
        return self._records[(workspace_id, record_id)]

    def act(self, record_id: str, payload: AuthorizationChainAction) -> AuthorizationChainRecord:
        op = (payload.workspace_id, payload.operation_id)
        if op in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(payload.workspace_id, record_id)
        transitions = {
            "verify": AuthorizationChainState.VERIFIED,
            "approve": AuthorizationChainState.APPROVED,
            "mark-eligible": AuthorizationChainState.ELIGIBLE,
            "revoke": AuthorizationChainState.REVOKED,
            "archive": AuthorizationChainState.ARCHIVED,
        }
        if payload.action not in transitions:
            raise ValueError("unsupported action")
        if payload.action == "verify" and record.risk_flags:
            raise ValueError("authorization chain findings block verification")
        if payload.action == "approve" and record.state != AuthorizationChainState.VERIFIED:
            raise ValueError("verified state required before approval")
        if payload.action == "mark-eligible" and record.state != AuthorizationChainState.APPROVED:
            raise ValueError("human approval required before dispatch eligibility")

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

    def _scores(self, payload: AuthorizationChainCreate) -> AuthorizationChainScores:
        links = payload.links
        expected_count = len(self.REQUIRED_STAGES)
        by_stage = {link.stage: link for link in links}
        continuity = sum(1 for stage in self.REQUIRED_STAGES if stage in by_stage) / expected_count
        approval_coverage = sum(1 for stage in self.REQUIRED_STAGES if by_stage.get(stage) and by_stage[stage].human_approved) / expected_count
        digest_coverage = sum(1 for stage in self.REQUIRED_STAGES if by_stage.get(stage) and len(by_stage[stage].digest) >= 8) / expected_count
        op_links = [link for link in links if link.operation]
        target_links = [link for link in links if link.target]
        operation_binding = 1.0 if op_links and all(link.operation == payload.expected_operation for link in op_links) else 0.0
        target_binding = 1.0 if target_links and all(link.target == payload.expected_target for link in target_links) else 0.0
        residual = min(1.0, (1 - continuity) * .25 + (1 - approval_coverage) * .25 + (1 - digest_coverage) * .15 + (1 - operation_binding) * .2 + (1 - target_binding) * .15)
        return AuthorizationChainScores(
            continuity=round(continuity, 4),
            approval_coverage=round(approval_coverage, 4),
            digest_coverage=round(digest_coverage, 4),
            operation_binding=operation_binding,
            target_binding=target_binding,
            residual_risk=round(residual, 4),
        )

    def _risk_flags(self, payload: AuthorizationChainCreate) -> List[str]:
        flags: List[str] = []
        by_stage = {link.stage: link for link in payload.links}
        for stage in self.REQUIRED_STAGES:
            link = by_stage.get(stage)
            if not link:
                flags.append(f"missing-stage:{stage}")
                continue
            if link.workspace_id != payload.workspace_id:
                flags.append(f"workspace-binding-mismatch:{stage}")
            if link.state not in self.ACCEPTED_STATES[stage]:
                flags.append(f"invalid-stage-state:{stage}:{link.state}")
            if link.risk_brain_blocked:
                flags += [f"upstream-risk-brain-block:{stage}", "risk-brain-hard-block"]
        for link in payload.links:
            if link.operation and link.operation != payload.expected_operation:
                flags.append(f"operation-binding-mismatch:{link.stage}")
            if link.target and link.target != payload.expected_target:
                flags.append(f"target-binding-mismatch:{link.stage}")
        if payload.expected_operation in self.PROTECTED_OPERATIONS:
            flags += [f"protected-operation:{payload.expected_operation}", "risk-brain-hard-block"]
        if any(flag.startswith(("workspace-binding-mismatch", "operation-binding-mismatch", "target-binding-mismatch", "invalid-stage-state")) for flag in flags) and payload.criticality >= .9:
            flags.append("risk-brain-hard-block")
        return sorted(set(flags))

    def _audit_event(self, record: AuthorizationChainRecord, action: str, actor: str, operation_id: str, detail: str | None = None) -> None:
        raw = f"{record.workspace_id}|{record.record_id}|{record.chain_digest}|{action}|{actor}|{operation_id}|{record.version}"
        self._audit.append({
            "workspace_id": record.workspace_id,
            "record_id": record.record_id,
            "action": action,
            "actor": actor,
            "operation_id": operation_id,
            "detail": detail,
            "event_digest": sha256(raw.encode()).hexdigest(),
        })


execution_authorization_chain_verification_service = ExecutionAuthorizationChainVerificationService()
