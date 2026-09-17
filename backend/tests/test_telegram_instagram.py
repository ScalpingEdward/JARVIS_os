"""Instagram approval from a phone -- and the guarantees around the buttons.

The gap this closes: 50 curated drafts sat pending and not one had ever
become a post, because finalizing a draft and approving the result were
reachable only by curl on the PC.

The one thing a tap must never do is publish. Approving records the
decision and stops, because Instagram's audio catalogue is unreachable from
the publishing path this account uses -- Brano picks the sound in the app
and posts Reels himself. A button that published on tap would take that
away silently.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.instagram_content.media_pool_models import MediaPoolIngestRequest, MediaPoolItemCreate
from app.instagram_content.media_pool_service import MediaPoolService
from app.instagram_content.models import ContentCandidateCreate, ContentStatus, MediaItem
from app.instagram_content.service import InstagramContentService
from app.notification_hub.telegram_delivery import TelegramDeliveryError
from app.telegram_instagram import tokens
from app.telegram_instagram.models import TelegramInstagramConfig
from app.telegram_instagram.service import TelegramInstagramError, TelegramInstagramService

SECRET = "instagram-callback-secret"
CHAT = "4242"
CAPTION = "The sea keeps its own time. #travel #coast #stillness"


class FakeTelegram:
    """Records what would have been sent, instead of reaching Telegram."""

    def __init__(self, fail_with: Exception | None = None) -> None:
        self.sent: list[tuple[str, list]] = []
        self.plain: list[str] = []
        self.fail_with = fail_with

    def send_with_keyboard(self, text: str, keyboard: list) -> int:
        if self.fail_with:
            raise self.fail_with
        self.sent.append((text, keyboard))
        return 900 + len(self.sent)

    def send(self, title: str, message: str) -> None:
        self.plain.append(message)

    def get_me(self) -> dict:
        return {"username": "auron_bot"}


@pytest.fixture(autouse=True)
def _clean():
    MediaPoolService().reset()
    InstagramContentService().reset()
    TelegramInstagramService().reset()
    yield


def _service(client: FakeTelegram | None = None, secret: str | None = SECRET, chat: str | None = CHAT):
    return TelegramInstagramService(
        config=TelegramInstagramConfig(callback_secret=secret, allowed_chat_id=chat),
        client=client or FakeTelegram(),
    )


def _candidate(status_proposed: bool = True):
    service = InstagramContentService()
    return service.propose(ContentCandidateCreate(
        media_items=[MediaItem(media_ref="clip", media_type="video", aesthetic_score=0.6, duration_seconds=20.0)],
        caption_draft=CAPTION,
    ))


def _tap(candidate_id: UUID, action: str, secret: str = SECRET, chat: str = CHAT) -> dict:
    return {
        "update_id": 1,
        "callback_query": {
            "id": "cb1",
            "from": {"id": 777},
            "message": {"chat": {"id": int(chat)}},
            "data": tokens.make_token(secret, candidate_id, action),
        },
    }


# -- tokens -----------------------------------------------------------------


def test_a_token_round_trips():
    cid = uuid4()
    assert tokens.verify_token(SECRET, tokens.make_token(SECRET, cid, tokens.PUBLISH_OK)) == (
        cid, tokens.PUBLISH_OK
    )


def test_a_token_signed_with_another_secret_is_refused():
    cid = uuid4()
    forged = tokens.make_token("some-other-secret", cid, tokens.PUBLISH_OK)
    with pytest.raises(tokens.TokenError, match="signature mismatch"):
        tokens.verify_token(SECRET, forged)


def test_the_trading_modules_action_letters_cannot_be_replayed_here():
    """The decisive isolation guarantee. telegram_approvals uses {a, r} and
    telegram_live_execution uses {x, c}; a token carrying either must not be
    accepted as an Instagram decision even if the secret were shared."""
    cid = uuid4()
    for foreign_action in ("a", "r", "x", "c"):
        with pytest.raises(tokens.TokenError, match="unknown action"):
            tokens.verify_token(SECRET, f"{cid}:{foreign_action}:whatever000")


# -- sending ----------------------------------------------------------------


def test_a_card_carries_the_caption_and_the_length_warning():
    service = InstagramContentService()
    candidate = service.propose(ContentCandidateCreate(
        media_items=[MediaItem(
            media_ref="long-clip", media_type="video", aesthetic_score=0.6, duration_seconds=46.0,
            recommended_trim_start_seconds=14.5, recommended_trim_end_seconds=41.2,
        )],
        caption_draft=CAPTION,
    ))
    client = FakeTelegram()
    _service(client).notify(candidate.id)

    text, keyboard = client.sent[0]
    assert "The sea keeps its own time" in text
    assert "14.5s-41.2s" in text, "the decision needs the trim window on the card"
    assert [b["text"] for b in keyboard[0]] == ["✅ Freigeben", "❌ Ablehnen"]


def test_no_card_goes_out_without_a_signing_secret():
    """A card whose buttons could not be verified is worse than no card."""
    candidate = _candidate()
    with pytest.raises(TelegramInstagramError, match="CALLBACK_SECRET"):
        _service(secret=None).notify(candidate.id)


def test_an_already_decided_candidate_is_not_offered_again():
    from app.instagram_content.models import ContentDecision

    candidate = _candidate()
    InstagramContentService().decide(candidate.id, ContentDecision(approved=True, reason="by hand"))

    with pytest.raises(TelegramInstagramError, match="not awaiting a decision"):
        _service().notify(candidate.id)


def test_a_delivery_failure_is_reported_and_recorded():
    candidate = _candidate()
    service = _service(FakeTelegram(fail_with=TelegramDeliveryError("telegram down")))

    with pytest.raises(TelegramInstagramError, match="could not deliver"):
        service.notify(candidate.id)
    assert any(r.action == "notify" and not r.success for r in service.audit_records())


# -- the queue --------------------------------------------------------------


def test_next_takes_the_oldest_shoot_day_first():
    """Posting order is the whole point of the queue: the oldest day is
    worked off before the next one starts."""
    from datetime import datetime, timezone

    from app.instagram_content.captured_at_resolution import CapturedAtSource

    pool = MediaPoolService()
    pool.ingest(MediaPoolIngestRequest(items=[
        MediaPoolItemCreate(
            media_ref="newer", media_type="video", theme="gym-clip", tags=["gym"],
            aesthetic_score=0.6, duration_seconds=20.0,
            captured_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
            captured_at_source=CapturedAtSource.filename,
        ),
        MediaPoolItemCreate(
            media_ref="older", media_type="video", theme="coast", tags=["sea"],
            aesthetic_score=0.6, duration_seconds=20.0,
            captured_at=datetime(2026, 2, 14, tzinfo=timezone.utc),
            captured_at_source=CapturedAtSource.filename,
        ),
    ]))
    pool.run_curation()

    client = FakeTelegram()
    result = _service(client).finalize_next_and_notify(caption_draft=CAPTION)

    from app.instagram_content.service import InstagramContentService as S
    candidate = S().get(result.candidate_id)
    assert candidate.media_items[0].media_ref == "older"


def test_next_refuses_politely_when_the_queue_is_empty():
    with pytest.raises(TelegramInstagramError, match="no pending drafts"):
        _service().finalize_next_and_notify(caption_draft=CAPTION)


# -- taps -------------------------------------------------------------------


def test_approving_records_the_decision_and_publishes_nothing():
    """The guarantee that matters most: approved, not posted."""
    candidate = _candidate()
    client = FakeTelegram()
    service = _service(client)

    decided = service.handle_update(_tap(candidate.id, tokens.PUBLISH_OK))

    assert decided is not None
    assert decided.status == ContentStatus.approved
    assert decided.published_media_id is None, "nothing may reach Instagram from a tap"
    assert any("selbst posten" in m for m in client.plain)


def test_declining_rejects_the_candidate():
    candidate = _candidate()
    decided = _service().handle_update(_tap(candidate.id, tokens.DECLINE))

    assert decided is not None
    assert decided.status == ContentStatus.rejected


def test_a_tap_from_another_chat_is_refused():
    """The primary defense: only the configured chat decides anything."""
    candidate = _candidate()
    service = _service()

    with pytest.raises(TelegramInstagramError, match="not allowed"):
        service.handle_update(_tap(candidate.id, tokens.PUBLISH_OK, chat="999999"))

    assert InstagramContentService().get(candidate.id).status == ContentStatus.proposed


def test_a_forged_token_is_refused_even_from_the_right_chat():
    candidate = _candidate()
    service = _service()

    with pytest.raises(TelegramInstagramError, match="rejected callback token"):
        service.handle_update(_tap(candidate.id, tokens.PUBLISH_OK, secret="wrong-secret"))

    assert InstagramContentService().get(candidate.id).status == ContentStatus.proposed


def test_a_second_tap_does_not_flip_an_already_decided_post():
    """Covers a double tap and a stale card: state is re-read at tap time,
    not trusted from the message."""
    candidate = _candidate()
    service = _service()
    service.handle_update(_tap(candidate.id, tokens.PUBLISH_OK))

    again = service.handle_update(_tap(candidate.id, tokens.DECLINE))

    assert again is not None
    assert again.status == ContentStatus.approved, "the first decision stands"


def test_an_ordinary_message_is_not_an_error():
    assert _service().handle_update({"update_id": 5, "message": {"text": "hallo"}}) is None


def test_every_tap_leaves_an_audit_trail():
    candidate = _candidate()
    service = _service()
    service.handle_update(_tap(candidate.id, tokens.PUBLISH_OK))

    records = service.audit_records()
    assert any(r.action == "decide" and r.success and r.actor == "777" for r in records)


# -- status -----------------------------------------------------------------


def test_status_reports_configuration_without_sending_anything():
    client = FakeTelegram()
    status = _service(client).status()

    assert status.callback_secret_configured is True
    assert status.allowed_chat_configured is True
    assert status.bot_username == "auron_bot"
    assert client.sent == [] and client.plain == []


def test_status_is_honest_when_nothing_is_configured():
    status = _service(secret=None, chat=None).status()

    assert status.callback_secret_configured is False
    assert status.allowed_chat_configured is False
