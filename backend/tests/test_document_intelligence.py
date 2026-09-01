import pytest
from pydantic import ValidationError

from app.document_intelligence.models import (
    AnalysisRequest,
    AnalysisState,
    AnalysisType,
    DocumentCreate,
    DocumentFormat,
    DocumentMutation,
    FieldDefinition,
)
from app.document_intelligence.service import DocumentIntelligenceService


def document_payload(key: str = "contract-1", workspace: str = "workspace-1", version: str = "1") -> DocumentCreate:
    return DocumentCreate(
        workspace_id=workspace,
        owner_id="owner-1",
        document_key=key,
        title="Service Contract",
        format=DocumentFormat.TXT,
        version=version,
        text_content=(
            "Service Contract. This agreement begins today.\n"
            "Customer: Phoenix GmbH\n"
            "Amount: 350 EUR\n"
            "Termination: Either party may terminate within 14 days.\n"
            "| Item | Price |\n"
            "| Hosting | 20 EUR |\n"
        ),
    )


def test_create_and_full_analysis():
    service = DocumentIntelligenceService()
    document = service.create_document(document_payload())
    result = service.analyze(
        AnalysisRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            document_id=document.id,
            analysis_type=AnalysisType.FULL,
            field_schema=[FieldDefinition(name="Customer", required=True), FieldDefinition(name="Amount")],
        )
    )
    assert result.state == AnalysisState.COMPLETED
    assert result.category.value == "contract"
    assert len(result.extracted_fields) == 2
    assert result.extracted_tables
    assert result.risks
    assert result.external_ai_used is False


def test_workspace_isolation_blocks_analysis():
    service = DocumentIntelligenceService()
    document = service.create_document(document_payload())
    result = service.analyze(
        AnalysisRequest(
            workspace_id="other-workspace",
            requester_id="owner-1",
            document_id=document.id,
        )
    )
    assert result.state == AnalysisState.BLOCKED


def test_duplicate_version_and_content_rejected():
    service = DocumentIntelligenceService()
    service.create_document(document_payload())
    with pytest.raises(ValueError):
        service.create_document(document_payload())
    with pytest.raises(ValueError):
        service.create_document(document_payload(key="copy", version="2"))


def test_owner_only_archive_and_restore():
    service = DocumentIntelligenceService()
    document = service.create_document(document_payload())
    assert service.set_active(document.id, "workspace-1", DocumentMutation(requester_id="wrong-owner"), False) is None
    archived = service.set_active(
        document.id,
        "workspace-1",
        DocumentMutation(requester_id="owner-1", reason="test"),
        False,
    )
    assert archived is not None and archived.active is False
    restored = service.set_active(document.id, "workspace-1", DocumentMutation(requester_id="owner-1"), True)
    assert restored is not None and restored.active is True


def test_compare_versions():
    service = DocumentIntelligenceService()
    old = service.create_document(document_payload(key="terms", version="1"))
    new_payload = document_payload(key="terms", version="2")
    new_payload.text_content += "Late fee: 50 EUR.\n"
    new = service.create_document(new_payload)
    result = service.analyze(
        AnalysisRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            document_id=new.id,
            comparison_document_id=old.id,
            analysis_type=AnalysisType.COMPARE,
        )
    )
    assert result.differences
    assert any(item.kind == "added" for item in result.differences)


def test_analysis_request_allows_external_ai_but_still_blocks_upload():
    service = DocumentIntelligenceService()
    document = service.create_document(document_payload())
    # use_external_ai is deliberately allowed now (2026-08-31) -- AURON's own
    # document analysis may use a real, opt-in Anthropic call; this must not
    # raise.
    request = AnalysisRequest(
        workspace_id="workspace-1",
        requester_id="owner-1",
        document_id=document.id,
        use_external_ai=True,
    )
    assert request.use_external_ai is True
    with pytest.raises(ValidationError):
        AnalysisRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            document_id=document.id,
            upload_document=True,
        )


def test_safety_rejects_cloud_upload_and_ocr():
    with pytest.raises(ValidationError):
        DocumentCreate(
            workspace_id="w",
            owner_id="o",
            document_key="cloud-file",
            title="Cloud file",
            format=DocumentFormat.TXT,
            automatic_cloud_upload=True,
        )
    with pytest.raises(ValidationError):
        DocumentCreate(
            workspace_id="w",
            owner_id="o",
            document_key="image",
            title="Scan",
            format=DocumentFormat.IMAGE,
            external_ocr_request=True,
        )


def test_status_reports_safety_defaults():
    status = DocumentIntelligenceService().status()
    assert status.version == "8.5"
    assert status.deterministic_local_analysis is True
    assert status.external_ai_execution is True  # real, opt-in capability as of 2026-08-31
    assert status.automatic_cloud_uploads is False
    assert status.external_ocr_execution is False
