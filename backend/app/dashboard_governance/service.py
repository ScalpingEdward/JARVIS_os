from datetime import datetime, timezone
from uuid import UUID

from .models import (
    DashboardGovernanceMetrics,
    DashboardGovernanceStatus,
    DashboardViewCreate,
    DashboardViewRecord,
    DashboardViewUpdate,
    ViewMutation,
    ViewState,
)


class DashboardGovernanceService:
    def __init__(self) -> None:
        self.views: dict[UUID, DashboardViewRecord] = {}
        self.audit: list[dict] = []

    def status(self) -> DashboardGovernanceStatus:
        return DashboardGovernanceStatus()

    def _audit(self, workspace_id: str, action: str, actor_id: str, entity_id: UUID | None = None) -> None:
        self.audit.append({
            "workspace_id": workspace_id,
            "action": action,
            "actor_id": actor_id,
            "entity_id": str(entity_id) if entity_id else None,
            "created_at": datetime.now(timezone.utc),
        })

    def create_view(self, payload: DashboardViewCreate) -> DashboardViewRecord:
        if any(
            item.workspace_id == payload.workspace_id and item.view_key == payload.view_key
            for item in self.views.values()
        ):
            raise ValueError("dashboard view key already exists in workspace")
        if payload.is_default:
            self._clear_default(payload.workspace_id)
        item = DashboardViewRecord(**payload.model_dump())
        self.views[item.id] = item
        self._audit(item.workspace_id, "dashboard-view.created", item.owner_id, item.id)
        return item

    def _clear_default(self, workspace_id: str, exclude_id: UUID | None = None) -> None:
        for item in self.views.values():
            if item.workspace_id == workspace_id and item.id != exclude_id and item.is_default:
                item.is_default = False
                item.updated_at = datetime.now(timezone.utc)

    def list_views(self, workspace_id: str, state: ViewState | None = None) -> list[DashboardViewRecord]:
        return [
            item for item in self.views.values()
            if item.workspace_id == workspace_id and (state is None or item.state == state)
        ]

    def get_view(self, view_id: UUID, workspace_id: str) -> DashboardViewRecord | None:
        item = self.views.get(view_id)
        if item is None or item.workspace_id != workspace_id:
            return None
        return item

    def update_view(
        self,
        view_id: UUID,
        workspace_id: str,
        payload: DashboardViewUpdate,
    ) -> DashboardViewRecord | None:
        item = self.get_view(view_id, workspace_id)
        if item is None:
            return None
        if item.state not in {ViewState.DRAFT, ViewState.REVIEW}:
            raise ValueError("published or archived views cannot be edited")
        if payload.requester_id != item.owner_id:
            raise ValueError("only the view owner can edit the view")
        updates = payload.model_dump(exclude={"requester_id"}, exclude_none=True)
        if updates.get("is_default") is True:
            self._clear_default(workspace_id, exclude_id=item.id)
        for field, value in updates.items():
            setattr(item, field, value)
        item.version += 1
        item.state = ViewState.DRAFT
        item.reviewed_by = None
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "dashboard-view.updated", payload.requester_id, item.id)
        return item

    def mutate_view(
        self,
        view_id: UUID,
        workspace_id: str,
        payload: ViewMutation,
        target: ViewState,
    ) -> DashboardViewRecord | None:
        item = self.get_view(view_id, workspace_id)
        if item is None:
            return None
        allowed = {
            ViewState.DRAFT: {ViewState.REVIEW, ViewState.ARCHIVED},
            ViewState.REVIEW: {ViewState.DRAFT, ViewState.PUBLISHED, ViewState.ARCHIVED},
            ViewState.PUBLISHED: {ViewState.ARCHIVED},
            ViewState.ARCHIVED: set(),
        }
        if target not in allowed[item.state]:
            raise ValueError("invalid dashboard view transition")
        if target == ViewState.REVIEW and payload.requester_id != item.owner_id:
            raise ValueError("only the owner can submit the view for review")
        if target == ViewState.PUBLISHED:
            if payload.requester_id == item.owner_id:
                raise ValueError("view owner cannot self-publish")
            item.reviewed_by = payload.requester_id
            item.published_by = payload.requester_id
            if item.is_default:
                self._clear_default(workspace_id, exclude_id=item.id)
        item.state = target
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"dashboard-view.{target.value}", payload.requester_id, item.id)
        return item

    def resolve_view(self, workspace_id: str, role: str | None = None) -> DashboardViewRecord | None:
        published = self.list_views(workspace_id, ViewState.PUBLISHED)
        eligible = [
            item for item in published
            if not item.audience_roles or (role is not None and role in item.audience_roles)
        ]
        defaults = [item for item in eligible if item.is_default]
        selected = defaults or eligible
        if not selected:
            return None
        return max(selected, key=lambda item: (item.version, item.updated_at))

    def metrics(self, workspace_id: str) -> DashboardGovernanceMetrics:
        views = self.list_views(workspace_id)
        return DashboardGovernanceMetrics(
            workspace_id=workspace_id,
            total_views=len(views),
            draft_views=sum(item.state == ViewState.DRAFT for item in views),
            review_views=sum(item.state == ViewState.REVIEW for item in views),
            published_views=sum(item.state == ViewState.PUBLISHED for item in views),
            archived_views=sum(item.state == ViewState.ARCHIVED for item in views),
            total_widgets=sum(len(item.widgets) for item in views),
            default_views=sum(item.is_default for item in views),
        )

    def list_audit(self, workspace_id: str) -> list[dict]:
        return [item for item in self.audit if item["workspace_id"] == workspace_id]


dashboard_governance_service = DashboardGovernanceService()
