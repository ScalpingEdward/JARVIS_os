from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class TrustState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    DRAFT = "draft"
    SCORED = "scored"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    HARDENING_QUEUED = "hardening-queued"
    HARDENING_APPLIED = "hardening-applied"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FAILED = "failed"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class TrustBand(str, Enum):
    UNTRUSTED = "untrusted"
    DEGRADED = "degraded"
    CONDITIONAL = "conditional"
    TRUSTED = "trusted"
    VERIFIED = "verified"


class TrustNode(BaseModel):
    node_id: str = Field(min_length=1, max_length=160)
    node_type: str = Field(pattern="^(configuration|artifact|runtime|rollback|deployment)$")
    version: str = Field(min_length=1, max_length=160)
    digest: str = Field(min_length=8, max_length=256)
    evidence_ref: str = Field(min_length=1, max_length=300)
    verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrustEdge(BaseModel):
    edge_id: str = Field(min_length=1, max_length=160)
    source_node_id: str = Field(min_length=1, max_length=160)
    target_node_id: str = Field(min_length=1, max_length=160)
    relation: str = Field(pattern="^(derived-from|deployed-as|rolled-back-to|verified-by|supersedes)$")
    confidence: float = Field(ge=0, le=1)
    evidence_ref: str = Field(min_length=1, max_length=300)


class HardeningControl(BaseModel):
    control_id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=200)
    current_value: str = Field(max_length=300)
    proposed_value: str = Field(max_length=300)
    expected_risk_reduction: float = Field(ge=0, le=1)
    requires_restart: bool = False
    evidence_ref: str = Field(min_length=1, max_length=300)


class TrustAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    rollback_assessment_id: str = Field(min_length=1, max_length=180)
    nodes: list[TrustNode] = Field(min_length=1)
    edges: list[TrustEdge] = Field(default_factory=list)
    controls: list[HardeningControl] = Field(default_factory=list)
    provenance_evidence_refs: list[str] = Field(min_length=1)
    runtime_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_graph(self) -> "TrustAssessmentCreate":
        node_ids = [item.node_id for item in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("node_id values must be unique")
        edge_ids = [item.edge_id for item in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("edge_id values must be unique")
        control_ids = [item.control_id for item in self.controls]
        if len(control_ids) != len(set(control_ids)):
            raise ValueError("control_id values must be unique")
        known = set(node_ids)
        for edge in self.edges:
            if edge.source_node_id not in known or edge.target_node_id not in known:
                raise ValueError("every trust edge must reference existing nodes")
            if edge.source_node_id == edge.target_node_id:
                raise ValueError("self-referencing trust edges are not allowed")
        return self


class TrustActionRequest(BaseModel):
    action: str = Field(pattern="^(score|request-review|approve|queue-hardening|apply-hardening|verify|reject|fail|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    applied_control_ids: list[str] = Field(default_factory=list)
    verification_evidence_refs: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: TrustState | None = None
    to_state: TrustState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class TrustAssessment(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    rollback_assessment_id: str
    nodes: list[TrustNode]
    edges: list[TrustEdge]
    controls: list[HardeningControl]
    provenance_evidence_refs: list[str]
    runtime_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: TrustState = TrustState.DRAFT
    trust_score: float = 0.0
    trust_band: TrustBand = TrustBand.UNTRUSTED
    unverified_node_count: int = 0
    approval_actor: str | None = None
    hardening_receipt_id: str | None = None
    applied_control_ids: list[str] = Field(default_factory=list)
    verification_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
