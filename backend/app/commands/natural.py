import re
from dataclasses import dataclass

from .models import CommandAction, CommandRequest


class NaturalLanguageParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedIntent:
    command: CommandRequest
    confidence: float


class NaturalLanguageParser:
    """Small deterministic parser for safe German and English commands.

    The parser only maps explicitly supported phrases to approved structured
    commands. It never executes arbitrary code or shell commands.
    """

    _status_patterns = (
        r"\b(projektstatus|status des projekts|zeige.*status)\b",
        r"\b(project status|show.*status)\b",
    )
    _assign_patterns = (
        r"\b(weise|ordne).*n[aä]chste[nr]?.*(worker|agent)\b",
        r"\b(assign).*next.*(worker|agent|task)\b",
    )
    _memory_prefixes = (
        "speichere, dass ",
        "speichere dass ",
        "merke dir, dass ",
        "merke dir dass ",
        "remember that ",
        "save that ",
    )
    _task_prefixes = (
        "erstelle eine aufgabe: ",
        "erstelle aufgabe: ",
        "neue aufgabe: ",
        "create a task: ",
        "create task: ",
    )

    def parse(self, text: str) -> ParsedIntent:
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            raise NaturalLanguageParseError("Command text is empty")
        normalized = cleaned.casefold()

        if self._matches_any(normalized, self._status_patterns):
            return ParsedIntent(
                command=CommandRequest(action=CommandAction.project_status),
                confidence=0.98,
            )

        if self._matches_any(normalized, self._assign_patterns):
            return ParsedIntent(
                command=CommandRequest(action=CommandAction.task_assign_next),
                confidence=0.95,
            )

        memory_content = self._strip_prefix(cleaned, normalized, self._memory_prefixes)
        if memory_content is not None:
            if not memory_content:
                raise NaturalLanguageParseError("Memory content is missing")
            return ParsedIntent(
                command=CommandRequest(
                    action=CommandAction.memory_create,
                    arguments={
                        "content": memory_content,
                        "category": "general",
                        "tags": ["natural-language"],
                        "priority": 2,
                    },
                ),
                confidence=0.92,
            )

        task_text = self._strip_prefix(cleaned, normalized, self._task_prefixes)
        if task_text is not None:
            title, description = self._task_parts(task_text)
            return ParsedIntent(
                command=CommandRequest(
                    action=CommandAction.task_create,
                    arguments={
                        "title": title,
                        "description": description,
                        "priority": 50,
                        "required_capabilities": [],
                    },
                ),
                confidence=0.90,
            )

        raise NaturalLanguageParseError("Command not recognized")

    @staticmethod
    def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, text) for pattern in patterns)

    @staticmethod
    def _strip_prefix(
        original: str,
        normalized: str,
        prefixes: tuple[str, ...],
    ) -> str | None:
        for prefix in prefixes:
            if normalized.startswith(prefix):
                return original[len(prefix) :].strip(" .")
        return None

    @staticmethod
    def _task_parts(text: str) -> tuple[str, str]:
        cleaned = text.strip(" .")
        if not cleaned:
            raise NaturalLanguageParseError("Task description is missing")
        if " - " in cleaned:
            title, description = cleaned.split(" - ", 1)
        else:
            title = cleaned[:200]
            description = cleaned
        return title.strip(), description.strip()


natural_language_parser = NaturalLanguageParser()
