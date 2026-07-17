from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ActionType,
    ApprovalRequest,
    DesktopActionCreate,
    DesktopActionRecord,
    DesktopAuditRecord,
    DesktopIntelligenceStatus,
    DesktopSessionCreate,
    DesktopSessionRecord,
    DesktopSnapshotCreate,
    DesktopSnapshotRecord,
    RiskLevel,
    SessionMutation,
    SessionState,
)


class DesktopIntelligenceService:
    def __init__(self) -> None:
        self.sessions: dict[UUID, DesktopSessionRecord] = {}
        self.snapshots: list[DesktopSnapshotRecord] = []
        self.actions: list[DesktopActionRecord] = []
        self.audit: list[DesktopAuditRecord] = []

    def status(self) -> DesktopIntelligenceStatus:
        return DesktopIntelligenceStatus(
            sessions=len(self.sessions),
            snapshots=len(self.snapshots),
            actions=len(self.actions),
            approved_actions=sum(item.approved for item in self.actions),
            blocked_actions=sum(item.blocked_reason is not None for item in self.actions),
        )

    def create_session(self, payload: DesktopSessionCreate) -> DesktopSessionRecord:
        if any(item.workspace_id == payload.workspace_id and item.session_key == payload.session_key for item in self.sessions.values()):
            raise ValueError("desktop session key already exists")
        item = DesktopSessionRecord(**payload.model_dump(exclude={"human_approved", "dry_run", "execute_desktop", "capture_credentials", "persist_clipboard"}))
        self.sessions[item.id] = item
        self._audit(item.workspace_id, item.owner_id, "session.created", "session", str(item.id), {})
        return item

    def list_sessions(self, workspace_id: str) -> list[DesktopSessionRecord]:
        return [item for item in self.sessions.values() if item.workspace_id == workspace_id]

    def get_session(self, session_id: UUID, workspace_id: str) -> DesktopSessionRecord | None:
        item = self.sessions.get(session_id)
        return item if item and item.workspace_id == workspace_id else None

    def mutate_session(self, session_id: UUID, workspace_id: str, payload: SessionMutation, state: SessionState) -> DesktopSessionRecord | None:
        item = self.get_session(session_id, workspace_id)
        if item is None or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, payload.requester_id, f"session.{state.value}", "session", str(item.id), {"reason": payload.reason})
        return item

    def add_snapshot(self, payload: DesktopSnapshotCreate) -> DesktopSnapshotRecord:
        session = self.get_session(payload.session_id, payload.workspace_id)
        if session is None:
            raise ValueError("desktop session not found")
        if payload.active_application.casefold() not in {name.casefold() for name in session.allowed_applications}:
            raise ValueError("application is outside the session allowlist")
        if any(item.workspace_id == payload.workspace_id and item.snapshot_hash == payload.snapshot_hash for item in self.snapshots):
            raise ValueError("duplicate desktop snapshot")
        item = DesktopSnapshotRecord(**payload.model_dump(exclude={"human_approved", "live_capture_performed"}))
        self.snapshots.append(item)
        self._audit(payload.workspace_id, session.owner_id, "snapshot.added", "snapshot", str(item.id), {"application": item.active_application})
        return item

    def list_snapshots(self, workspace_id: str, session_id: UUID | None = None) -> list[DesktopSnapshotRecord]:
        return [item for item in self.snapshots if item.workspace_id == workspace_id and (session_id is None or item.session_id == session_id)]

    def plan_action(self, payload: DesktopActionCreate) -> DesktopActionRecord:
        session = self.get_session(payload.session_id, payload.workspace_id)
        if session is None:
            raise ValueError("desktop session not found")
        if session.state in {SessionState.CANCELLED, SessionState.BLOCKED}:
            raise ValueError("desktop session cannot accept actions")
        if session.step_count >= session.maximum_steps:
            session.state = SessionState.BLOCKED
            session.blocked_reason = "maximum step count reached"
            raise ValueError(session.blocked_reason)
        if payload.target_application and payload.target_application.casefold() not in {name.casefold() for name in session.allowed_applications}:
            raise ValueError("application is outside the session allowlist")

        risk = payload.risk_level
        if payload.action in {ActionType.TYPE_TEXT, ActionType.HOTKEY, ActionType.OPEN_APP, ActionType.CLOSE_APP} and risk == RiskLevel.LOW:
            risk = RiskLevel.MEDIUM
        if payload.action in {ActionType.SAVE, ActionType.DELETE}:
            risk = RiskLevel.CRITICAL

        value_preview = payload.value_preview
        if payload.action == ActionType.TYPE_TEXT and value_preview:
            value_preview = "[REDACTED INPUT]"

        approval_required = payload.requires_human_approval or risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
        item = DesktopActionRecord(
            workspace_id=payload.workspace_id,
            session_id=payload.session_id,
            action=payload.action,
            target_application=payload.target_application,
            target_element_id=payload.target_element_id,
            value_preview=value_preview,
            rationale=payload.rationale,
            risk_level=risk,
            requires_human_approval=approval_required,
            approved=payload.human_approved if approval_required else True,
        )
        self.actions.append(item)
        session.step_count += 1
        self._audit(payload.workspace_id, session.owner_id, "action.planned", "action", str(item.id), {"risk": risk.value})
        return item

    def list_actions(self, workspace_id: str, session_id: UUID | None = None) -> list[DesktopActionRecord]:
        return [item for item in self.actions if item.workspace_id == workspace_id and (session_id is None or item.session_id == session_id)]

    def approve_action(self, action_id: UUID, workspace_id: str, payload: ApprovalRequest) -> DesktopActionRecord | None:
        item = next((candidate for candidate in self.actions if candidate.id == action_id and candidate.workspace_id == workspace_id), None)
        if item is None:
            return None
        session = self.get_session(item.session_id, workspace_id)
        if session is None or session.owner_id != payload.requester_id:
            return None
        item.approved = payload.approved
        item.blocked_reason = None if payload.approved else (payload.reason or "human approval denied")
        self._audit(workspace_id, payload.requester_id, "action.approved" if payload.approved else "action.denied", "action", str(item.id), {"reason": payload.reason})
        return item

    def list_audit(self, workspace_id: str) -> list[DesktopAuditRecord]:
        return [item for item in self.audit if item.workspace_id == workspace_id]

    def _audit(self, workspace_id: str, actor_id: str, action: str, object_type: str, object_id: str, details: dict) -> None:
        self.audit.append(DesktopAuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, object_type=object_type, object_id=object_id, details=details))


desktop_intelligence_service = DesktopIntelligenceService()
