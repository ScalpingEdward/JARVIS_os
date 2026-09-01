import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.instagram_content.models import ContentCandidateCreate, ContentDecision, ContentStatus, PostFormat
from app.instagram_content.publisher import N8nInstagramPublisher, N8nInstagramPublisherError
from app.instagram_content.service import InstagramContentError, InstagramContentService
from app.main import app

api_client = TestClient(app)


def _image(ref="drive://file-123", score=0.9):
    return {"media_ref": ref, "media_type": "image", "aesthetic_score": score}


def _video(ref="drive://clip-1", score=0.9, duration=20.0):
    return {"media_ref": ref, "media_type": "video", "aesthetic_score": score, "duration_seconds": duration}


def _candidate_payload(**overrides):
    payload = dict(
        media_items=[_image()],
        caption_draft="Build in silence. Let the results make the noise.",
        aesthetic_notes="Clean composition, matches the high-end aesthetic.",
    )
    payload.update(overrides)
    return payload


def _service_with_mock_publisher(handler):
    transport = httpx.MockTransport(handler)
    publisher = N8nInstagramPublisher(client=httpx.Client(transport=transport))
    return InstagramContentService(publisher=publisher)


# -- format decision, wired through propose() --------------------------------


def test_single_image_becomes_single_post():
    service = InstagramContentService()
    item = service.propose(ContentCandidateCreate(**_candidate_payload(media_items=[_image()])))
    assert item.post_format == PostFormat.single_image


def test_single_video_becomes_a_reel():
    service = InstagramContentService()
    item = service.propose(ContentCandidateCreate(**_candidate_payload(media_items=[_video()])))
    assert item.post_format == PostFormat.reel


def test_multiple_images_become_a_carousel():
    service = InstagramContentService()
    item = service.propose(
        ContentCandidateCreate(**_candidate_payload(media_items=[_image("a"), _image("b"), _image("c")]))
    )
    assert item.post_format == PostFormat.carousel


def test_mixed_image_and_video_still_becomes_a_carousel():
    service = InstagramContentService()
    item = service.propose(ContentCandidateCreate(**_candidate_payload(media_items=[_image("a"), _video("b")])))
    assert item.post_format == PostFormat.carousel


def test_carousel_is_capped_at_ten_items():
    with pytest.raises(Exception):  # pydantic ValidationError
        ContentCandidateCreate(**_candidate_payload(media_items=[_image(str(i)) for i in range(11)]))


def test_video_requires_a_duration():
    with pytest.raises(Exception):
        ContentCandidateCreate(
            **_candidate_payload(media_items=[{"media_ref": "x", "media_type": "video", "aesthetic_score": 0.9}])
        )


# -- edit plan ----------------------------------------------------------------


def test_edit_plan_gives_every_item_the_same_grade_preset():
    service = InstagramContentService()
    item = service.propose(
        ContentCandidateCreate(**_candidate_payload(media_items=[_image("a"), _image("b"), _video("c")]))
    )
    presets = {instruction.color_grade_preset for instruction in item.edit_plan}
    assert len(presets) == 1  # one consistent look across the whole account


def test_edit_plan_flags_an_overlong_reel_for_trimming_without_inventing_a_window():
    service = InstagramContentService()
    item = service.propose(ContentCandidateCreate(**_candidate_payload(media_items=[_video("c", duration=120.0)])))
    instruction = item.edit_plan[0]
    assert instruction.trim_needed is True
    assert instruction.trim_start_seconds is None  # never invented
    assert instruction.trim_end_seconds is None


def test_edit_plan_does_not_flag_a_well_sized_reel():
    service = InstagramContentService()
    item = service.propose(ContentCandidateCreate(**_candidate_payload(media_items=[_video("c", duration=20.0)])))
    assert item.edit_plan[0].trim_needed is False


# -- hook check -----------------------------------------------------------


def test_hook_warning_for_hashtag_opening():
    service = InstagramContentService()
    item = service.propose(ContentCandidateCreate(**_candidate_payload(caption_draft="#mystic #trading vibes only")))
    assert any("hashtag" in w.lower() for w in item.hook_warnings)


def test_no_hook_warning_for_a_solid_opening_line():
    service = InstagramContentService()
    item = service.propose(
        ContentCandidateCreate(**_candidate_payload(caption_draft="Most people quit right before it clicks."))
    )
    assert item.hook_warnings == []


# -- approval / publish flow, unchanged in spirit, updated for new schema --


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


def test_publish_records_a_permanent_knowledge_graph_node():
    from app.knowledge_graph.service import knowledge_graph_service

    knowledge_graph_service.reset()
    service = _service_with_mock_publisher(lambda request: httpx.Response(200, json={"media_id": "17895695668004550"}))
    item = service.propose(ContentCandidateCreate(**_candidate_payload(caption_draft="Quiet mornings. #tradingmindset #discipline")))
    service.decide(item.id, ContentDecision(approved=True, reason="Good"))
    service.publish(item.id)

    nodes = knowledge_graph_service.search_nodes("tradingmindset", kind="event")
    assert len(nodes) == 1
    assert "instagram" in nodes[0].tags
    assert nodes[0].properties["media_id"] == "17895695668004550"


def test_publish_failure_does_not_record_a_knowledge_graph_node():
    from app.knowledge_graph.service import knowledge_graph_service

    knowledge_graph_service.reset()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream error")

    service = _service_with_mock_publisher(handler)
    item = service.propose(ContentCandidateCreate(**_candidate_payload(caption_draft="Never posted. #tradingmindset")))
    service.decide(item.id, ContentDecision(approved=True, reason="Approved"))
    with pytest.raises(InstagramContentError):
        service.publish(item.id)

    nodes = knowledge_graph_service.search_nodes("tradingmindset", kind="event")
    assert nodes == []


def test_approved_publish_sends_media_items_format_and_edit_plan_to_n8n():
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"media_id": "17895695668004550"})

    service = _service_with_mock_publisher(handler)
    item = service.propose(ContentCandidateCreate(**_candidate_payload(media_items=[_image("a"), _image("b")])))
    service.decide(item.id, ContentDecision(approved=True, reason="Great pair"))

    result = service.publish(item.id)

    assert result.status == ContentStatus.posted
    assert result.published_media_id == "17895695668004550"
    assert len(calls) == 1
    assert calls[0]["post_format"] == "carousel"
    assert [m["media_ref"] for m in calls[0]["media_items"]] == ["a", "b"]
    assert len(calls[0]["edit_plan"]) == 2
    assert calls[0]["edit_plan"][0]["color_grade_preset"]


def test_n8n_failure_marks_post_failed_and_does_not_retry_silently():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream error")

    service = _service_with_mock_publisher(handler)
    item = service.propose(ContentCandidateCreate(**_candidate_payload()))
    service.decide(item.id, ContentDecision(approved=True, reason="Approved"))

    with pytest.raises(InstagramContentError):
        service.publish(item.id)

    assert service.get(item.id).status == ContentStatus.post_failed


def test_publish_failure_sends_a_high_priority_notification():
    from app.notification_hub.models import DeliveryPriority
    from app.notification_hub.service import notification_hub_service

    notification_hub_service.reset()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream error")

    service = _service_with_mock_publisher(handler)
    item = service.propose(ContentCandidateCreate(**_candidate_payload()))
    service.decide(item.id, ContentDecision(approved=True, reason="Approved"))
    with pytest.raises(InstagramContentError):
        service.publish(item.id)

    matching = [n for n in notification_hub_service.list_all() if n.source_id == str(item.id) and "failed" in n.title.lower()]
    assert len(matching) == 1
    assert matching[0].priority == DeliveryPriority.high
    assert matching[0].requires_acknowledgement is True


def test_publisher_rejects_missing_media_id_in_response():
    from app.instagram_content.edit_plan import build_edit_plan
    from app.instagram_content.format_decision import decide_format
    from app.instagram_content.models import MediaItem

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    publisher = N8nInstagramPublisher(client=httpx.Client(transport=httpx.MockTransport(handler)))
    media_items = [MediaItem(**_image())]
    post_format, _ = decide_format(media_items)
    edit_plan = build_edit_plan(media_items, post_format)
    with pytest.raises(N8nInstagramPublisherError, match="media_id"):
        publisher.publish(media_items, post_format, edit_plan, "caption", "req-1")


def test_proposing_a_candidate_notifies_via_notification_hub():
    from app.notification_hub.models import DeliveryState
    from app.notification_hub.service import notification_hub_service

    notification_hub_service.reset()
    service = InstagramContentService()
    item = service.propose(ContentCandidateCreate(**_candidate_payload()))

    notifications = notification_hub_service.list_all()
    matching = [n for n in notifications if n.source_id == str(item.id)]
    assert len(matching) == 1
    assert matching[0].domain == "instagram"
    assert "ready for review" in matching[0].title.lower()
    assert matching[0].state in (DeliveryState.delivered, DeliveryState.deferred)


def test_moderation_rejected_candidate_sends_a_low_priority_notification():
    from app.notification_hub.models import DeliveryPriority
    from app.notification_hub.service import notification_hub_service

    notification_hub_service.reset()
    service = InstagramContentService()
    item = service.propose(ContentCandidateCreate(**_candidate_payload(caption_draft="Follow4follow please!!")))
    assert item.status == ContentStatus.moderation_rejected

    notifications = notification_hub_service.list_all()
    matching = [n for n in notifications if n.source_id == str(item.id)]
    assert len(matching) == 1
    assert matching[0].priority == DeliveryPriority.low
    assert "auto-rejected" in matching[0].title.lower()


def test_api_flow_end_to_end():
    from app.instagram_content.service import instagram_content_service

    instagram_content_service.reset()
    created = api_client.post("/v1/instagram/candidates", json=_candidate_payload())
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    assert created.json()["post_format"] == "single_image"

    listed = api_client.get("/v1/instagram/candidates", params={"status": "proposed"})
    assert listed.json()["count"] == 1

    premature_publish = api_client.post(f"/v1/instagram/candidates/{candidate_id}/publish")
    assert premature_publish.status_code == 409

    decided = api_client.post(
        f"/v1/instagram/candidates/{candidate_id}/decision",
        json={"approved": True, "reason": "Looks great"},
    )
    assert decided.json()["status"] == "approved"


def test_history_search_via_the_api(monkeypatch):
    from app.instagram_content.service import instagram_content_service
    from app.knowledge_graph.service import knowledge_graph_service

    instagram_content_service.reset()
    knowledge_graph_service.reset()

    def fake_publish(media_items, post_format, edit_plan, caption, request_id):
        return "17895695668004550"

    monkeypatch.setattr(instagram_content_service._publisher, "publish", fake_publish)

    created = api_client.post(
        "/v1/instagram/candidates",
        json=_candidate_payload(caption_draft="Desert mornings. #tradingmindset #discipline"),
    )
    candidate_id = created.json()["id"]
    api_client.post(f"/v1/instagram/candidates/{candidate_id}/decision", json={"approved": True, "reason": "Good"})
    publish_response = api_client.post(f"/v1/instagram/candidates/{candidate_id}/publish")
    assert publish_response.status_code == 200

    search_response = api_client.get("/v1/instagram/history/search", params={"query": "tradingmindset"})
    assert search_response.status_code == 200
    results = search_response.json()
    assert len(results) == 1
    assert "instagram" in results[0]["tags"]


def test_posting_schedule_endpoint():
    response = api_client.get("/v1/instagram/posting-schedule/0")
    assert response.status_code == 200
    body = response.json()
    assert body["windows"]
    assert "analytics" in body["note"].lower() or "insights" in body["note"].lower()

    invalid = api_client.get("/v1/instagram/posting-schedule/9")
    assert invalid.status_code == 422
