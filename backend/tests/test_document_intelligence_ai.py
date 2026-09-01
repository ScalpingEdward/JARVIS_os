from __future__ import annotations

import json

import httpx
import pytest

from app.document_intelligence.document_ai_analyzer import (
    AnthropicDocumentAnalyzer,
    DocumentAIAnalysisConfig,
    DocumentAIAnalysisError,
)
from app.document_intelligence.models import AnalysisRequest, AnalysisState, AnalysisType, DocumentCreate, DocumentFormat
from app.document_intelligence.service import DocumentIntelligenceService


def _ai_response(**overrides) -> httpx.Response:
    payload = {
        "category": "contract",
        "category_confidence": 0.9,
        "summary": "A services agreement between two parties.",
        "risks": ["Termination clause is one-sided."],
        "key_points": ["Effective date is January 1.", "Governing law is Germany."],
    }
    payload.update(overrides)
    return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps(payload)}]})


# -- AnthropicDocumentAnalyzer: real, bounded call ----------------------------


def test_analyze_fails_closed_without_an_api_key():
    analyzer = AnthropicDocumentAnalyzer(config=DocumentAIAnalysisConfig(api_key=None))
    with pytest.raises(DocumentAIAnalysisError, match="ANTHROPIC_API_KEY is not set"):
        analyzer.analyze("Title", "Some text.", 5)


def test_analyze_returns_the_parsed_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ai_response()

    analyzer = AnthropicDocumentAnalyzer(
        config=DocumentAIAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    result = analyzer.analyze("Services Agreement", "This agreement...", 5)
    assert result.category == "contract"
    assert result.category_confidence == pytest.approx(0.9)
    assert "services agreement" in result.summary.lower()
    assert result.risks == ["Termination clause is one-sided."]
    assert len(result.key_points) == 2


def test_analyze_sends_the_real_document_text():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _ai_response()

    analyzer = AnthropicDocumentAnalyzer(
        config=DocumentAIAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    analyzer.analyze("My Title", "The quick brown fox contract text.", 3)

    prompt = captured["body"]["messages"][0]["content"]
    assert "My Title" in prompt
    assert "quick brown fox contract text" in prompt


def test_analyze_raises_on_invalid_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": "not json"}]})

    analyzer = AnthropicDocumentAnalyzer(
        config=DocumentAIAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(DocumentAIAnalysisError, match="not valid JSON"):
        analyzer.analyze("Title", "Text", 5)


def test_analyze_raises_on_missing_required_field():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps({"category": "contract"})}]})

    analyzer = AnthropicDocumentAnalyzer(
        config=DocumentAIAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(DocumentAIAnalysisError, match="missing required field"):
        analyzer.analyze("Title", "Text", 5)


def test_analyze_raises_on_api_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid x-api-key")

    analyzer = AnthropicDocumentAnalyzer(
        config=DocumentAIAnalysisConfig(api_key="bad-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(DocumentAIAnalysisError, match="401"):
        analyzer.analyze("Title", "Text", 5)


# -- DocumentIntelligenceService: opt-in wiring, fails closed on AI failure --


def _document_payload(**overrides):
    base = dict(
        workspace_id="workspace-1",
        owner_id="owner-1",
        document_key="doc-1",
        title="Services Agreement",
        format=DocumentFormat.TXT,
        text_content="This Services Agreement is entered into between Acme and Client, effective January 1.",
    )
    base.update(overrides)
    return DocumentCreate(**base)


def test_service_uses_ai_result_when_requested():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ai_response()

    service = DocumentIntelligenceService(
        ai_analyzer=AnthropicDocumentAnalyzer(
            config=DocumentAIAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
        )
    )
    document = service.create_document(_document_payload())
    record = service.analyze(
        AnalysisRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            document_id=document.id,
            analysis_type=AnalysisType.FULL,
            use_external_ai=True,
        )
    )
    assert record.state == AnalysisState.COMPLETED
    assert record.external_ai_used is True
    assert "services agreement" in record.summary.lower()
    assert any(r.code == "ai-flagged" for r in record.risks)
    assert len(record.ai_key_points) == 2


def test_service_does_not_call_ai_when_not_requested():
    class ExplodingAnalyzer:
        def analyze(self, *args, **kwargs):
            raise AssertionError("AI analyzer must not be called when use_external_ai is False")

    service = DocumentIntelligenceService(ai_analyzer=ExplodingAnalyzer())
    document = service.create_document(_document_payload())
    record = service.analyze(
        AnalysisRequest(
            workspace_id="workspace-1", requester_id="owner-1", document_id=document.id, analysis_type=AnalysisType.FULL
        )
    )
    assert record.state == AnalysisState.COMPLETED
    assert record.external_ai_used is False


def test_service_fails_closed_when_ai_analysis_errors_rather_than_falling_back_silently():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream error")

    service = DocumentIntelligenceService(
        ai_analyzer=AnthropicDocumentAnalyzer(
            config=DocumentAIAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
        )
    )
    document = service.create_document(_document_payload())
    record = service.analyze(
        AnalysisRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            document_id=document.id,
            analysis_type=AnalysisType.FULL,
            use_external_ai=True,
        )
    )
    assert record.state == AnalysisState.FAILED
    assert record.blocked_reason is not None
    assert "AI-based analysis failed" in record.blocked_reason
    # critically: did NOT silently return a completed record using only
    # the deterministic fallback and pretend the AI request succeeded
    assert record.summary == ""
