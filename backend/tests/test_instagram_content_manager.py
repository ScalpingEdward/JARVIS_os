import httpx
import pytest
from fastapi.testclient import TestClient

from app.instagram_content.models import ContentCandidateCreate, ContentDecision, ContentStatus
from app.instagram_content.publisher import N8nInstagramPublisher, N8nInstagramPublisherError
from app.instagram_content.service import InstagramContentError, InstagramContentService
from app.main import app

api_client = TestClient(app)


def _candidate_payload(**overrides):
    payload = dict(
        image_source_ref="drive://file-123",
        caption_draft="Build in silence.",
        aesthetic_score=0.9,
        aesthetic_notes="Clean composition, matches the high-end aesthetic.",
    )
    payload.update(overrides)
    return payload


def _service_with_mock_publisher(handler):
    transport = httpx.MockTransport(handler)
    publisher = N8nInstagramPublisher(client=httpx.Client(transport=transport))
    return InstagramContentService(publisher=publisher)


def test_publish_is_blocked_before_approval():
    service = _service_with_mock_publisher(lambda request: httpx.Response(200, json={"media_id": "should-not-be-called"}))
    item = service.propose(ContentCandidateCreate(**_candidate_payload()))
    with pytest.raises(InstagramContentError, match="must be explicitly approved first"):
        service.publish(item.id)


def test_rejected_candidate_cannot_be_published():
    service = _service_with_mock_publisher(lambda request: httpx.Response(200, json={"media_id": "x"}))
    item = service.propose(ContentCandidateCreate(**_candidate_payload()))
    service.decide(item.id, ContentDecision(approved=False, reason="Doesn't fit the feed grid"))
    assert item.status == ContentStatus.rejected
    with pytest.raises(InstagramContentError):
        service.publish(item.id)


def test_approval_can_edit_the_caption():
    service = _service_with_mock_publisher(lambda request: httpx.Response(200, json={"media_id": "x"}))
    item = service.propose(ContentCandidateCreate(**_candidate_payload()))
    service.decide(
        item.id,
        ContentDecision(approved=True, reason="Good pick", edited_caption="Quiet confidence. Nothing to prove."),
    )
    assert item.caption_draft == "Quiet confidence. Nothing to prove."
    assert item.status == ContentStatus.approved


def test_approved_publish_calls_n8n_and_records_media_id():
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"media_id": "17895695668004550"})

    service = _service_with_mock_publisher(handler)
    item = service.propose(ContentCandidateCreate(**_candidate_payload()))
    service.decide(item.id, ContentDecision(approved=True, reason="Great shot"))

    result = service.publish(item.id)

    assert result.status == ContentStatus.posted
    assert result.published_media_id == "17895695668004550"
    assert len(calls) == 1
    assert calls[0]["image_source_ref"] == "drive://file-123"


def test_n8n_failure_marks_post_failed_and_does_not_retry_silently():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream error")

    service = _service_with_mock_publisher(handler)
    item = service.propose(ContentCandidateCreate(**_candidate_payload()))
    service.decide(item.id, ContentDecision(approved=True, reason="Approved"))

    with pytest.raises(InstagramContentError):
        service.publish(item.id)

    assert service.get(item.id).status == ContentStatus.post_failed


def test_publisher_rejects_missing_media_id_in_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    publisher = N8nInstagramPublisher(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(N8nInstagramPublisherError, match="media_id"):
        publisher.publish("drive://x", "caption", "req-1")


def test_api_flow_end_to_end():
    from app.instagram_content.service import instagram_content_service

    instagram_content_service.reset()
    created = api_client.post("/v1/instagram/candidates", json=_candidate_payload())
    assert created.status_code == 200
    candidate_id = created.json()["id"]

    listed = api_client.get("/v1/instagram/candidates", params={"status": "proposed"})
    assert listed.json()["count"] == 1

    premature_publish = api_client.post(f"/v1/instagram/candidates/{candidate_id}/publish")
    assert premature_publish.status_code == 409

    decided = api_client.post(
        f"/v1/instagram/candidates/{candidate_id}/decision",
        json={"approved": True, "reason": "Looks great"},
    )
    assert decided.json()["status"] == "approved"
