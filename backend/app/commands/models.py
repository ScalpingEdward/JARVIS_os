from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CommandAction(StrEnum):
    memory_create = "memory.create"
    task_create = "task.create"
    task_assign_next = "task.assign_next"
    project_status = "project.status"


class CommandRequest(BaseModel):
    action: CommandAction
    arguments: dict[str, Any] = Field(default_factory=dict)


class CommandResponse(BaseModel):
    action: CommandAction
    status: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class NaturalLanguageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    execute: bool = True


class NaturalLanguageResponse(BaseModel):
    recognized: bool
    confidence: float = Field(ge=0.0, le=1.0)
    command: CommandRequest
    result: CommandResponse | None = None
