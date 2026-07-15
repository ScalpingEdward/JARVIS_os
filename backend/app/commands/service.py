from pydantic import ValidationError

from app.memory.models import MemoryCreate
from app.memory.service import memory_service
from app.orchestrator.models import TaskCreate
from app.orchestrator.service import orchestrator_service

from .models import CommandAction, CommandRequest, CommandResponse


class CommandExecutionError(ValueError):
    pass


class CommandService:
    def execute(self, command: CommandRequest) -> CommandResponse:
        try:
            if command.action == CommandAction.memory_create:
                record = memory_service.create(MemoryCreate.model_validate(command.arguments))
                return CommandResponse(
                    action=command.action,
                    status="completed",
                    message="Memory created",
                    data=record.model_dump(mode="json"),
                )

            if command.action == CommandAction.task_create:
                task = orchestrator_service.create_task(TaskCreate.model_validate(command.arguments))
                return CommandResponse(
                    action=command.action,
                    status="completed",
                    message="Task created",
                    data=task.model_dump(mode="json"),
                )

            if command.action == CommandAction.task_assign_next:
                task = orchestrator_service.assign_next()
                if task is None:
                    raise CommandExecutionError("No compatible task and agent available")
                return CommandResponse(
                    action=command.action,
                    status="completed",
                    message="Next task assigned",
                    data=task.model_dump(mode="json"),
                )

            if command.action == CommandAction.project_status:
                snapshot = orchestrator_service.status()
                return CommandResponse(
                    action=command.action,
                    status="completed",
                    message="Project status loaded",
                    data=snapshot.model_dump(mode="json"),
                )

        except ValidationError as exc:
            raise CommandExecutionError(str(exc)) from exc

        raise CommandExecutionError(f"Unsupported command: {command.action}")


command_service = CommandService()
