from collections import defaultdict, deque
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ApprovalRequest,
    AuditRecord,
    CircuitState,
    CommandCreate,
    CommandRecord,
    CommandState,
    EventState,
    HealthUpdate,
    IntegrationEventCreate,
    IntegrationEventRecord,
    IntegrationHubStatus,
    ModuleHealth,
    ModuleRecord,
    ModuleRegistrationCreate,
    ReplayRequest,
    SubscriptionCreate,
    SubscriptionRecord,
)


class IntegrationHubService:
    def __init__(self) -> None:
        self.modules: dict[UUID, ModuleRecord] = {}
        self.events: dict[UUID, IntegrationEventRecord] = {}
        self.subscriptions: dict[UUID, SubscriptionRecord] = {}
        self.commands: dict[UUID, CommandRecord] = {}
        self.audit: list[AuditRecord] = []
        self._sequence: defaultdict[str, int] = defaultdict(int)
        self._event_windows: defaultdict[tuple[str, str], deque[datetime]] = defaultdict(deque)

    def _audit(self, workspace_id: str, actor_id: str, action: str, object_type: str, object_id: str, **details: object) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, object_type=object_type, object_id=object_id, details=details))

    def create_module(self, payload: ModuleRegistrationCreate) -> ModuleRecord:
        if any(item.workspace_id == payload.workspace_id and item.module_key == payload.module_key for item in self.modules.values()):
            raise ValueError("module key already exists in workspace")
        item = ModuleRecord(**payload.model_dump(exclude={"human_approved", "external_endpoint", "automatic_external_connection"}))
        self.modules[item.id] = item
        self._audit(item.workspace_id, item.owner_id, "module.registered", "module", str(item.id), module_key=item.module_key)
        return item

    def list_modules(self, workspace_id: str) -> list[ModuleRecord]:
        return [item for item in self.modules.values() if item.workspace_id == workspace_id]

    def get_module(self, module_id: UUID, workspace_id: str) -> ModuleRecord | None:
        item = self.modules.get(module_id)
        return item if item and item.workspace_id == workspace_id else None

    def _module_by_key(self, workspace_id: str, module_key: str) -> ModuleRecord | None:
        return next((item for item in self.modules.values() if item.workspace_id == workspace_id and item.module_key == module_key and item.active), None)

    def update_health(self, module_id: UUID, workspace_id: str, payload: HealthUpdate) -> ModuleRecord | None:
        item = self.get_module(module_id, workspace_id)
        if item is None or item.owner_id != payload.requester_id:
            return None
        item.health = payload.health
        item.updated_at = datetime.now(timezone.utc)
        if payload.health == ModuleHealth.HEALTHY:
            item.failure_count = 0
            item.circuit_state = CircuitState.CLOSED
        elif payload.health == ModuleHealth.UNAVAILABLE:
            item.failure_count += 1
            if item.failure_count >= item.failure_threshold:
                item.circuit_state = CircuitState.OPEN
        else:
            item.circuit_state = CircuitState.HALF_OPEN
        self._audit(workspace_id, payload.requester_id, "module.health_updated", "module", str(item.id), health=item.health.value, circuit=item.circuit_state.value, reason=payload.reason)
        return item

    def create_subscription(self, payload: SubscriptionCreate) -> SubscriptionRecord:
        module = self._module_by_key(payload.workspace_id, payload.subscriber_module)
        if module is None or module.owner_id != payload.owner_id:
            raise ValueError("owned subscriber module not found")
        item = SubscriptionRecord(**payload.model_dump(exclude={"human_approved", "automatic_external_action"}))
        self.subscriptions[item.id] = item
        self._audit(item.workspace_id, item.owner_id, "subscription.created", "subscription", str(item.id), event_types=item.event_types)
        return item

    def list_subscriptions(self, workspace_id: str) -> list[SubscriptionRecord]:
        return [item for item in self.subscriptions.values() if item.workspace_id == workspace_id]

    def _rate_limited(self, module: ModuleRecord) -> bool:
        now = datetime.now(timezone.utc)
        window = self._event_windows[(module.workspace_id, module.module_key)]
        cutoff = now.timestamp() - 60
        while window and window[0].timestamp() < cutoff:
            window.popleft()
        if len(window) >= module.rate_limit_per_minute:
            return True
        window.append(now)
        return False

    def publish_event(self, payload: IntegrationEventCreate) -> IntegrationEventRecord:
        module = self._module_by_key(payload.workspace_id, payload.publisher_module)
        if module is None:
            raise ValueError("publisher module not found")
        if module.circuit_state == CircuitState.OPEN or module.health == ModuleHealth.UNAVAILABLE:
            raise ValueError("publisher module circuit is open")
        if payload.event_type not in module.published_events:
            raise ValueError("event type is not declared by publisher module")
        self._sequence[payload.workspace_id] += 1
        state = EventState.RATE_LIMITED if self._rate_limited(module) else EventState.ACCEPTED
        item = IntegrationEventRecord(**payload.model_dump(exclude={"human_approved", "dispatch_external"}), state=state, sequence=self._sequence[payload.workspace_id])
        self.events[item.id] = item
        self._audit(item.workspace_id, module.owner_id, "event.published", "event", str(item.id), event_type=item.event_type, state=item.state.value)
        return item

    def list_events(self, workspace_id: str, event_type: str | None = None) -> list[IntegrationEventRecord]:
        items = [item for item in self.events.values() if item.workspace_id == workspace_id]
        if event_type:
            items = [item for item in items if item.event_type == event_type]
        return sorted(items, key=lambda item: item.sequence)

    def replay_events(self, payload: ReplayRequest) -> list[IntegrationEventRecord]:
        replayed: list[IntegrationEventRecord] = []
        for event_id in payload.event_ids:
            source = self.events.get(event_id)
            if source is None or source.workspace_id != payload.workspace_id:
                continue
            self._sequence[payload.workspace_id] += 1
            item = IntegrationEventRecord(
                workspace_id=source.workspace_id,
                publisher_module=source.publisher_module,
                event_type=source.event_type,
                subject=source.subject,
                payload=source.payload,
                correlation_id=source.correlation_id,
                causation_id=source.id,
                priority=source.priority,
                state=EventState.REPLAYED,
                sequence=self._sequence[payload.workspace_id],
                replay_of=source.id,
            )
            self.events[item.id] = item
            replayed.append(item)
            self._audit(item.workspace_id, payload.requester_id, "event.replayed", "event", str(item.id), replay_of=str(source.id))
        return replayed

    def create_command(self, payload: CommandCreate) -> CommandRecord:
        source = self._module_by_key(payload.workspace_id, payload.source_module)
        target = self._module_by_key(payload.workspace_id, payload.target_module)
        if source is None or target is None:
            raise ValueError("source or target module not found")
        if target.circuit_state == CircuitState.OPEN or target.health == ModuleHealth.UNAVAILABLE:
            state = CommandState.BLOCKED
            blocked_reason = "target module circuit is open"
        elif payload.command_name not in target.accepted_commands:
            state = CommandState.BLOCKED
            blocked_reason = "command is not declared by target module"
        else:
            state = CommandState.PLANNED
            blocked_reason = None
        item = CommandRecord(**payload.model_dump(exclude={"human_approved", "dry_run", "execute_command"}), state=state, blocked_reason=blocked_reason)
        self.commands[item.id] = item
        self._audit(item.workspace_id, item.requester_id, "command.planned", "command", str(item.id), state=item.state.value, target=item.target_module)
        return item

    def list_commands(self, workspace_id: str) -> list[CommandRecord]:
        return [item for item in self.commands.values() if item.workspace_id == workspace_id]

    def approve_command(self, command_id: UUID, workspace_id: str, payload: ApprovalRequest) -> CommandRecord | None:
        item = self.commands.get(command_id)
        if item is None or item.workspace_id != workspace_id or item.requester_id != payload.requester_id or item.state == CommandState.BLOCKED:
            return None
        item.approved = payload.approved
        item.state = CommandState.APPROVED if payload.approved else CommandState.REJECTED
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, payload.requester_id, "command.approval_recorded", "command", str(item.id), approved=payload.approved, reason=payload.reason)
        return item

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit if item.workspace_id == workspace_id]

    def status(self) -> IntegrationHubStatus:
        modules = list(self.modules.values())
        commands = list(self.commands.values())
        return IntegrationHubStatus(
            modules=len(modules),
            healthy_modules=sum(item.health == ModuleHealth.HEALTHY for item in modules),
            degraded_modules=sum(item.health == ModuleHealth.DEGRADED for item in modules),
            unavailable_modules=sum(item.health == ModuleHealth.UNAVAILABLE for item in modules),
            open_circuits=sum(item.circuit_state == CircuitState.OPEN for item in modules),
            events=len(self.events),
            subscriptions=len(self.subscriptions),
            commands=len(commands),
            planned_commands=sum(item.state == CommandState.PLANNED for item in commands),
            approved_commands=sum(item.state == CommandState.APPROVED for item in commands),
        )


integration_hub_service = IntegrationHubService()
