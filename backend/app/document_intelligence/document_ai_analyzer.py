from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import httpx

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

MAX_DOCUMENT_CHARS_FOR_AI = 60_000  # keeps a single call well within a reasonable prompt size


class DocumentAIAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentAIAnalysisConfig:
    api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    model: str = field(default_factory=lambda: os.getenv("AURON_DOCUMENT_MODEL", "claude-sonnet-5"))
    timeout_seconds: float = 60.0
    max_tokens: int = 2000


@dataclass(frozen=True)
class DocumentAIAnalysisResult:
    category: str
    category_confidence: float
    summary: str
    risks: list[str]
    key_points: list[str]


class AnthropicDocumentAnalyzer:
    """Real document understanding via a bounded Anthropic call -- reads
    the document's actual text and reasons about it, instead of the
    keyword/regex heuristics in service.py's _classify/_summarize/
    _find_risks. Opt-in only (AnalysisRequest.use_external_ai=True):
    document content leaves the process for this call, unlike the
    deterministic local methods, so it is never the silent default.

    Fails closed: no API key, a transport/API error, or a response that
    isn't valid JSON with every required field all raise rather than
    returning a fabricated analysis.
    """

    def __init__(self, config: DocumentAIAnalysisConfig | None = None, client: httpx.Client | None = None) -> None:
        self.config = config or DocumentAIAnalysisConfig()
        self._client = client

    def analyze(self, title: str, text: str, maximum_summary_sentences: int) -> DocumentAIAnalysisResult:
        if not self.config.api_key:
            raise DocumentAIAnalysisError(
                "ANTHROPIC_API_KEY is not set -- AURON cannot run AI-based document analysis without it. "
                "Local deterministic analysis (classify/summarize/extract by keyword and regex) still works "
                "without it; this is an opt-in enhancement, not a requirement."
            )

        truncated = text[:MAX_DOCUMENT_CHARS_FOR_AI]
        truncation_note = "" if len(text) <= MAX_DOCUMENT_CHARS_FOR_AI else (
            f"\n\n[Document truncated to the first {MAX_DOCUMENT_CHARS_FOR_AI} characters for this analysis.]"
        )

        prompt = (
            f"Analyze this document titled '{title}'.\n\n"
            f"Document text:\n{truncated}{truncation_note}\n\n"
            "Respond with ONLY a JSON object, no other text, no markdown fences:\n"
            '{"category": "contract|invoice|report|manual|legal|trading|business|personal|technical|unknown", '
            '"category_confidence": 0.0, '
            f'"summary": "up to {maximum_summary_sentences} sentences", '
            '"risks": ["specific risk or concern found in the text, if any"], '
            '"key_points": ["specific factual point actually stated in the text"]}\n\n'
            "Only include a risk or key point if the text actually supports it -- do not invent content "
            "that isn't in the document."
        )

        client, should_close = (self._client, False) if self._client else (httpx.Client(), True)
        try:
            response = client.post(
                ANTHROPIC_MESSAGES_URL,
                headers={
                    "x-api-key": self.config.api_key,
                    "anthropic-version": ANTHROPIC_API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "max_tokens": self.config.max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self.config.timeout_seconds,
            )
            if response.status_code >= 400:
                raise DocumentAIAnalysisError(f"Anthropic API returned {response.status_code}: {response.text[:500]}")
            data = response.json()
            blocks = data.get("content", [])
            text_parts = [block["text"] for block in blocks if block.get("type") == "text"]
            raw = "".join(text_parts).strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.lower().startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise DocumentAIAnalysisError(f"Model response was not valid JSON: {raw[:300]}") from exc

            required = ["category", "category_confidence", "summary", "risks", "key_points"]
            missing = [key for key in required if key not in parsed]
            if missing:
                raise DocumentAIAnalysisError(f"Response missing required field(s) {missing}: {parsed}")

            return DocumentAIAnalysisResult(
                category=str(parsed["category"]),
                category_confidence=float(parsed["category_confidence"]),
                summary=str(parsed["summary"]),
                risks=[str(r) for r in parsed["risks"]],
                key_points=[str(p) for p in parsed["key_points"]],
            )
        except httpx.HTTPError as exc:
            raise DocumentAIAnalysisError(f"Could not reach the Anthropic API: {exc}") from exc
        finally:
            if should_close:
                client.close()
