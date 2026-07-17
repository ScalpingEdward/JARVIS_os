from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord, CompatibilityState, DependencyCreate, DependencyRecord,
    GraphRecord, HealthUpdate, ImpactRecord, ImpactRequest, Mutation,
    RegistryStatus, ServiceCreate, ServiceRecord, ServiceState,
)


class ServiceRegistryService:
    def __init__(self) -> None:
        self.services: dict[UUID, ServiceRecord] = {}
        self.dependencies: dict[UUID, DependencyRecord] = {}
        self.impacts: dict[UUID, ImpactRecord] = {}
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, **details) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, action=action, entity_type=entity_type, entity_id=entity_id, actor_id=actor_id, details=details))

    @staticmethod
    def _version_tuple(value: str) -> tuple[int, ...] | None:
        try:
            return tuple(int(part) for part in value.lstrip("v").split("."))
        except ValueError:
            return None

    def _compatibility(self, target: ServiceRecord, minimum: str | None, maximum: str | None) -> CompatibilityState:
        current = self._version_tuple(target.version)
        low = self._version_tuple(minimum) if minimum else None
        high = self._version_tuple(maximum) if maximum else None
        if current is None or (minimum and low is None) or (maximum and high is None):
            return CompatibilityState.UNKNOWN
        if low is not None and current < low:
            return CompatibilityState.INCOMPATIBLE
        if high is not None and current > high:
            return CompatibilityState.INCOMPATIBLE
        return CompatibilityState.COMPATIBLE

    def _cycles(self, workspace_id: str, extra: tuple[UUID, UUID] | None = None) -> list[list[UUID]]:
        graph: dict[UUID, list[UUID]] = {item.id: [] for item in self.services.values() if item.workspace_id == workspace_id}
        for edge in self.dependencies.values():
            if edge.workspace_id == workspace_id:
                graph.setdefault(edge.source_service_id, []).append(edge.target_service_id)
        if extra:
            graph.setdefault(extra[0], []).append(extra[1])
        cycles: list[list[UUID]] = []
        visiting: set[UUID] = set()
        visited: set[UUID] = set()
        path: list[UUID] = []

        def visit(node: UUID) -> None:
            if node in visiting:
                start = path.index(node)
                cycle = path[start:] + [node]
                if cycle not in cycles:
                    cycles.append(cycle)
                return
            if node in visited:
                return
            visiting.add(node)
            path.append(node)
            for child in graph.get(node, []):
                visit(child)
            path.pop()
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)
        return cycles

    def status(self) -> RegistryStatus:
        workspaces = {item.workspace_id for item in self.services.values()}
        cycle_count = sum(len(self._cycles(workspace)) for workspace in workspaces)
        return RegistryStatus(services=len(self.services), dependencies=len(self.dependencies), impacts=len(self.impacts), cycles_detected=cycle_count)

    def create_service(self, payload: ServiceCreate) -> ServiceRecord:
        if any(item.workspace_id == payload.workspace_id and item.service_key == payload.service_key and item.state != ServiceState.RETIRED for item in self.services.values()):
            raise ValueError("active service key already exists")
        item = ServiceRecord(**payload.model_dump())
        self.services[item.id] = item
        self._audit(item.workspace_id, "service.created", "service", item.id, item.owner_id, service_key=item.service_key, version=item.version)
        return item

    def list_services(self, workspace_id: str) -> list[ServiceRecord]:
        return [item for item in self.services.values() if item.workspace_id == workspace_id]

    def get_service(self, service_id: UUID, workspace_id: str) -> ServiceRecord | None:
        item = self.services.get(service_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_service_state(self, service_id: UUID, workspace_id: str, payload: Mutation, state: ServiceState) -> ServiceRecord | None:
        item = self.services.get(service_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"service.{state.value}", "service", item.id, payload.requester_id, reason=payload.reason)
        return item

    def update_health(self, service_id: UUID, workspace_id: str, payload: HealthUpdate) -> ServiceRecord | None:
        item = self.services.get(service_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.health = payload.state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "service.health_updated", "service", item.id, payload.requester_id, state=payload.state.value, reason=payload.reason)
        return item

    def create_dependency(self, payload: DependencyCreate) -> DependencyRecord:
        source = self.services.get(payload.source_service_id)
        target = self.services.get(payload.target_service_id)
        if not source or not target or source.workspace_id != payload.workspace_id or target.workspace_id != payload.workspace_id:
            raise ValueError("workspace services not found")
        if source.owner_id != payload.owner_id:
            raise ValueError("dependency owner must own the source service")
        if any(item.workspace_id == payload.workspace_id and item.source_service_id == payload.source_service_id and item.target_service_id == payload.target_service_id and item.kind == payload.kind for item in self.dependencies.values()):
            raise ValueError("dependency already exists")
        if self._cycles(payload.workspace_id, (payload.source_service_id, payload.target_service_id)):
            raise ValueError("dependency would create a cycle")
        item = DependencyRecord(**payload.model_dump(), compatibility=self._compatibility(target, payload.minimum_version, payload.maximum_version))
        self.dependencies[item.id] = item
        self._audit(item.workspace_id, "dependency.created", "dependency", item.id, item.owner_id, source=str(item.source_service_id), target=str(item.target_service_id), compatibility=item.compatibility.value)
        return item

    def list_dependencies(self, workspace_id: str) -> list[DependencyRecord]:
        return [item for item in self.dependencies.values() if item.workspace_id == workspace_id]

    def graph(self, workspace_id: str) -> GraphRecord:
        return GraphRecord(workspace_id=workspace_id, nodes=self.list_services(workspace_id), edges=self.list_dependencies(workspace_id), cycles=self._cycles(workspace_id))

    def impact(self, payload: ImpactRequest) -> ImpactRecord:
        root = self.services.get(payload.service_id)
        if not root or root.workspace_id != payload.workspace_id:
            raise ValueError("workspace service not found")
        affected: set[UUID] = set()
        queue = [payload.service_id]
        incompatible: list[UUID] = []
        while queue:
            target_id = queue.pop(0)
            for edge in self.dependencies.values():
                if edge.workspace_id != payload.workspace_id or edge.target_service_id != target_id:
                    continue
                if not payload.include_optional and edge.kind.value == "optional":
                    continue
                if edge.source_service_id not in affected:
                    affected.add(edge.source_service_id)
                    queue.append(edge.source_service_id)
                if edge.compatibility == CompatibilityState.INCOMPATIBLE:
                    incompatible.append(edge.id)
        risk = min(100, len(affected) * 12 + len(payload.changed_routes) * 4 + len(payload.changed_events) * 3 + len(incompatible) * 20)
        item = ImpactRecord(workspace_id=payload.workspace_id, service_id=payload.service_id, affected_service_ids=sorted(affected, key=str), affected_routes=payload.changed_routes, affected_events=payload.changed_events, incompatible_dependencies=incompatible, risk_score=risk)
        self.impacts[item.id] = item
        self._audit(payload.workspace_id, "impact.analyzed", "impact", item.id, "system", affected=len(affected), risk_score=risk)
        return item

    def list_capabilities(self, workspace_id: str) -> list[dict]:
        return [{"service_id": item.id, "service_key": item.service_key, "version": item.version, "api_routes": item.api_routes, "produces_events": item.produces_events, "consumes_events": item.consumes_events, "permissions": item.permissions} for item in self.list_services(workspace_id)]

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit if item.workspace_id == workspace_id]


service_registry_service = ServiceRegistryService()
