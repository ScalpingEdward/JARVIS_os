from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID

from .models import (
    ActionType,
    BrowserAuditRecord,
    BrowserIntelligenceStatus,
    BrowserSessionCreate,
    BrowserSessionRecord,
    ElementKind,
    NavigationStepCreate,
    NavigationStepRecord,
    PageAnalysisRecord,
    PageAnalysisRequest,
    PageSnapshotCreate,
    PageSnapshotRecord,
    RiskLevel,
    SessionMutation,
    SessionState,
    StepApproval,
)


class BrowserIntelligenceService:
    def __init__(self) -> None:
        self.sessions: dict[UUID, BrowserSessionRecord] = {}
        self.snapshots: dict[UUID, PageSnapshotRecord] = {}
        self.steps: dict[UUID, NavigationStepRecord] = {}
        self.analyses: dict[UUID, PageAnalysisRecord] = {}
        self.audit: list[BrowserAuditRecord] = []

    def status(self) -> BrowserIntelligenceStatus:
        return BrowserIntelligenceStatus(
            sessions=len(self.sessions),
            active_sessions=sum(item.state == SessionState.ACTIVE for item in self.sessions.values()),
            snapshots=len(self.snapshots),
            planned_steps=len(self.steps),
            approved_steps=sum(item.human_approved for item in self.steps.values()),
            analyses=len(self.analyses),
        )

    def create_session(self, payload: BrowserSessionCreate) -> BrowserSessionRecord:
        if any(
            item.workspace_id == payload.workspace_id and item.session_key == payload.session_key
            for item in self.sessions.values()
        ):
            raise ValueError("session key already exists in workspace")
        start_url = str(payload.start_url)
        domain = self._domain(start_url)
        allowed = [value.lower().strip() for value in payload.allowed_domains]
        if not self._domain_allowed(domain, allowed):
            raise ValueError("start URL domain is not in the allowlist")
        record = BrowserSessionRecord(
            workspace_id=payload.workspace_id,
            owner_id=payload.owner_id,
            session_key=payload.session_key,
            start_url=start_url,
            current_url=start_url,
            allowed_domains=allowed,
            maximum_steps=payload.maximum_steps,
        )
        self.sessions[record.id] = record
        self._audit(record.workspace_id, record.owner_id, "session.created", "session", record.id)
        return record

    def list_sessions(self, workspace_id: str) -> list[BrowserSessionRecord]:
        return [item for item in self.sessions.values() if item.workspace_id == workspace_id]

    def get_session(self, session_id: UUID, workspace_id: str) -> BrowserSessionRecord | None:
        session = self.sessions.get(session_id)
        return session if session and session.workspace_id == workspace_id else None

    def activate_session(
        self, session_id: UUID, workspace_id: str, payload: SessionMutation
    ) -> BrowserSessionRecord | None:
        session = self._owned_session(session_id, workspace_id, payload.requester_id)
        if session is None or session.state in {SessionState.CANCELLED, SessionState.COMPLETED}:
            return None
        session.state = SessionState.ACTIVE
        session.updated_at = self._now()
        self._audit(workspace_id, payload.requester_id, "session.activated", "session", session.id, payload.reason)
        return session

    def pause_session(
        self, session_id: UUID, workspace_id: str, payload: SessionMutation
    ) -> BrowserSessionRecord | None:
        session = self._owned_session(session_id, workspace_id, payload.requester_id)
        if session is None or session.state != SessionState.ACTIVE:
            return None
        session.state = SessionState.PAUSED
        session.updated_at = self._now()
        self._audit(workspace_id, payload.requester_id, "session.paused", "session", session.id, payload.reason)
        return session

    def cancel_session(
        self, session_id: UUID, workspace_id: str, payload: SessionMutation
    ) -> BrowserSessionRecord | None:
        session = self._owned_session(session_id, workspace_id, payload.requester_id)
        if session is None or session.state == SessionState.COMPLETED:
            return None
        session.state = SessionState.CANCELLED
        session.updated_at = self._now()
        self._audit(workspace_id, payload.requester_id, "session.cancelled", "session", session.id, payload.reason)
        return session

    def add_snapshot(self, payload: PageSnapshotCreate) -> PageSnapshotRecord:
        session = self.get_session(payload.session_id, payload.workspace_id)
        if session is None:
            raise ValueError("session not found")
        domain = self._domain(str(payload.url))
        if not self._domain_allowed(domain, session.allowed_domains):
            raise ValueError("snapshot URL domain is outside the session allowlist")
        if any(
            item.session_id == payload.session_id and item.dom_hash == payload.dom_hash
            for item in self.snapshots.values()
        ):
            raise ValueError("duplicate snapshot DOM hash for session")
        record = PageSnapshotRecord(
            workspace_id=payload.workspace_id,
            session_id=payload.session_id,
            url=str(payload.url),
            title=payload.title,
            text_content=payload.text_content,
            dom_hash=payload.dom_hash,
            elements=payload.elements,
            screenshot_reference=payload.screenshot_reference,
            metadata=payload.metadata,
        )
        self.snapshots[record.id] = record
        session.current_url = record.url
        session.updated_at = self._now()
        self._audit(payload.workspace_id, session.owner_id, "snapshot.added", "snapshot", record.id)
        return record

    def list_snapshots(self, workspace_id: str, session_id: UUID | None = None) -> list[PageSnapshotRecord]:
        return [
            item
            for item in self.snapshots.values()
            if item.workspace_id == workspace_id and (session_id is None or item.session_id == session_id)
        ]

    def plan_step(self, payload: NavigationStepCreate) -> NavigationStepRecord:
        session = self.get_session(payload.session_id, payload.workspace_id)
        if session is None:
            raise ValueError("session not found")
        if session.state in {SessionState.CANCELLED, SessionState.COMPLETED, SessionState.BLOCKED}:
            raise ValueError("session does not accept new steps")
        existing = [item for item in self.steps.values() if item.session_id == session.id]
        if len(existing) >= session.maximum_steps:
            session.state = SessionState.BLOCKED
            session.blocked_reason = "maximum step count reached"
            raise ValueError(session.blocked_reason)
        target_url = str(payload.target_url) if payload.target_url else None
        blocked_reason: str | None = None
        if target_url and not self._domain_allowed(self._domain(target_url), session.allowed_domains):
            blocked_reason = "target URL domain is outside the session allowlist"
        if payload.action in {ActionType.SUBMIT, ActionType.UPLOAD, ActionType.DOWNLOAD}:
            risk = RiskLevel.CRITICAL
        elif payload.action in {ActionType.TYPE, ActionType.CLICK, ActionType.SELECT}:
            risk = max(payload.risk_level, RiskLevel.HIGH, key=self._risk_rank)
        else:
            risk = payload.risk_level
        record = NavigationStepRecord(
            workspace_id=payload.workspace_id,
            session_id=session.id,
            ordinal=len(existing),
            action=payload.action,
            target_url=target_url,
            element_id=payload.element_id,
            value_preview=self._redact(payload.value_preview),
            rationale=payload.rationale,
            risk_level=risk,
            requires_human_approval=payload.requires_human_approval,
            human_approved=payload.human_approved,
            blocked_reason=blocked_reason,
        )
        self.steps[record.id] = record
        session.step_count = len(existing) + 1
        session.updated_at = self._now()
        self._audit(payload.workspace_id, session.owner_id, "step.planned", "step", record.id, blocked_reason or "")
        return record

    def list_steps(self, workspace_id: str, session_id: UUID | None = None) -> list[NavigationStepRecord]:
        return [
            item
            for item in self.steps.values()
            if item.workspace_id == workspace_id and (session_id is None or item.session_id == session_id)
        ]

    def approve_step(self, step_id: UUID, workspace_id: str, payload: StepApproval) -> NavigationStepRecord | None:
        step = self.steps.get(step_id)
        if step is None or step.workspace_id != workspace_id or step.blocked_reason:
            return None
        session = self.get_session(step.session_id, workspace_id)
        if session is None or session.owner_id != payload.approved_by:
            return None
        step.human_approved = payload.approved
        if not payload.approved:
            step.blocked_reason = payload.reason or "human approval denied"
        self._audit(workspace_id, payload.approved_by, "step.approval", "step", step.id, payload.reason)
        return step

    def analyze_page(self, payload: PageAnalysisRequest) -> PageAnalysisRecord:
        snapshot = self.snapshots.get(payload.snapshot_id)
        if snapshot is None or snapshot.workspace_id != payload.workspace_id:
            raise ValueError("snapshot not found")
        forms = sum(item.kind == ElementKind.FORM for item in snapshot.elements)
        tables = sum(item.kind == ElementKind.TABLE for item in snapshot.elements)
        sensitive = sum(item.sensitive for item in snapshot.elements)
        objective_tokens = {token.lower() for token in payload.objective.split() if len(token) > 2}
        suggested = [
            item.element_id
            for item in snapshot.elements
            if item.visible
            and item.enabled
            and not item.sensitive
            and any(token in item.label.lower() for token in objective_tokens)
        ][:20]
        summary = (
            f"Page '{snapshot.title or snapshot.url}' contains {len(snapshot.elements)} indexed elements, "
            f"{forms} forms, {tables} tables and {sensitive} sensitive elements. "
            "Analysis used supplied snapshot data only."
        )
        record = PageAnalysisRecord(
            workspace_id=payload.workspace_id,
            snapshot_id=snapshot.id,
            requester_id=payload.requester_id,
            objective=payload.objective,
            summary=summary,
            detected_forms=forms,
            detected_tables=tables,
            detected_sensitive_elements=sensitive,
            suggested_element_ids=suggested,
        )
        self.analyses[record.id] = record
        self._audit(payload.workspace_id, payload.requester_id, "page.analyzed", "analysis", record.id)
        return record

    def list_analyses(self, workspace_id: str) -> list[PageAnalysisRecord]:
        return [item for item in self.analyses.values() if item.workspace_id == workspace_id]

    def list_audit(self, workspace_id: str) -> list[BrowserAuditRecord]:
        return [item for item in self.audit if item.workspace_id == workspace_id]

    def _owned_session(self, session_id: UUID, workspace_id: str, requester_id: str) -> BrowserSessionRecord | None:
        session = self.get_session(session_id, workspace_id)
        return session if session and session.owner_id == requester_id else None

    def _audit(self, workspace_id: str, actor_id: str, action: str, resource_type: str, resource_id: UUID, detail: str = "") -> None:
        self.audit.append(
            BrowserAuditRecord(
                workspace_id=workspace_id,
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail,
            )
        )

    @staticmethod
    def _domain(url: str) -> str:
        return (urlparse(url).hostname or "").lower()

    @staticmethod
    def _domain_allowed(domain: str, allowed_domains: list[str]) -> bool:
        return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in allowed_domains)

    @staticmethod
    def _risk_rank(level: RiskLevel) -> int:
        return {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}[level]

    @staticmethod
    def _redact(value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) <= 4:
            return "***"
        return f"{value[:2]}***{value[-2:]}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)


browser_intelligence_service = BrowserIntelligenceService()
