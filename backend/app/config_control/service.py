from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ComponentConfig,
    ComponentConfigCreate,
    ConfigState,
    ControlPlaneStatus,
    ReadinessCheck,
)


class ConfigurationControlService:
    def __init__(self) -> None:
        self._components: dict[UUID, ComponentConfig] = {}

    def reset(self) -> None:
        self._components.clear()

    def create(self, payload: ComponentConfigCreate) -> ComponentConfig:
        record = ComponentConfig(**payload.model_dump())
        self._components[record.id] = record
        return self.validate(record.id)

    def list_all(self) -> list[ComponentConfig]:
        return sorted(self._components.values(), key=lambda item: item.name.lower())

    def get(self, component_id: UUID) -> ComponentConfig | None:
        return self._components.get(component_id)

    def validate(self, component_id: UUID) -> ComponentConfig:
        record = self._components[component_id]
        missing = [ref.name for ref in record.secret_references if ref.required and not os.getenv(ref.name)]
        messages: list[str] = []
        if not record.enabled:
            state = ConfigState.disabled
            messages.append("Component is disabled")
        elif missing:
            state = ConfigState.degraded
            messages.append("Required secret references are not available in the runtime environment")
        else:
            state = ConfigState.ready
            messages.append("Configuration contract is ready")
        record = record.model_copy(
            update={
                "state": state,
                "missing_secrets": missing,
                "validation_messages": messages,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._components[component_id] = record
        return record.model_copy(deep=True)

    def validate_all(self) -> list[ReadinessCheck]:
        checks: list[ReadinessCheck] = []
        for component_id in list(self._components):
            record = self.validate(component_id)
            checks.append(
                ReadinessCheck(
                    component_id=record.id,
                    component_name=record.name,
                    ready=record.state == ConfigState.ready,
                    state=record.state,
                    missing_secrets=record.missing_secrets,
                    messages=record.validation_messages,
                )
            )
        return checks

    def status(self) -> ControlPlaneStatus:
        self.validate_all()
        items = list(self._components.values())
        return ControlPlaneStatus(
            total_components=len(items),
            ready_components=sum(item.state == ConfigState.ready for item in items),
            degraded_components=sum(item.state == ConfigState.degraded for item in items),
            disabled_components=sum(item.state == ConfigState.disabled for item in items),
            missing_secret_references=sum(len(item.missing_secrets) for item in items),
        )


configuration_control_service = ConfigurationControlService()
