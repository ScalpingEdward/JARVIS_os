import pytest

from app.approvals.models import ActorRole, ApprovalRequestCreate, ApprovalStatus, RiskLevel
from app.approvals.service import approval_service
from app.mobile.service import mobile_control_service
from app.voice.models import TelegramVoiceRequest, VoiceIntent, VoiceSettings, VoiceTranscriptRequest
from app.voice.service import VoiceControlError, voice_control_service


def setup_function() -> None:
    approval_service.reset()
    mobile_control_service.reset()
    mobile_control_service.set_authorized_users({77})
    voice_control_service.reset()
    voice_control_service.configure(VoiceSettings(assistant_name="PHOENIX", wake_name="phoenix"))


def request(transcript: str, user_id: int = 77):
    return VoiceTranscriptRequest(telegram_user_id=user_id, chat_id=100, transcript=transcript)


def test_assistant_name_and_wake_name_are_freely_configurable() -> None:
    settings = voice_control_service.configure(
        VoiceSettings(assistant_name="ARANEA", wake_name="aranea", language="de-DE")
    )
    reply = voice_control_service.handle_transcript(request("Aranea Status"))
    assert settings.assistant_name == "ARANEA"
    assert reply.assistant_name == "ARANEA"
    assert reply.intent == VoiceIntent.status


def test_missing_wake_name_is_rejected() -> None:
    with pytest.raises(VoiceControlError, match="Wake-Name"):
        voice_control_service.handle_transcript(request("Status"))


def test_pause_and_resume_use_existing_safe_mobile_control() -> None:
    paused = voice_control_service.handle_transcript(request("Phoenix Pause"))
    assert paused.intent == VoiceIntent.pause
    assert mobile_control_service.execution_allowed() is False
    resumed = voice_control_service.handle_transcript(request("Phoenix Weiter"))
    assert resumed.intent == VoiceIntent.resume
    assert mobile_control_service.execution_allowed() is True


def test_critical_approval_requires_second_voice_confirmation() -> None:
    approval = approval_service.request(
        ApprovalRequestCreate(
            action="release.deploy",
            requested_by="planner",
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason="Release candidate ready",
        )
    )
    first = voice_control_service.handle_transcript(request(f"Phoenix freigeben {approval.id}"))
    assert first.requires_confirmation is True
    assert first.confirmation_id is not None
    assert approval_service.get(approval.id).status == ApprovalStatus.pending

    confirmed = voice_control_service.handle_transcript(
        request(f"Phoenix bestätigen {first.confirmation_id}")
    )
    assert confirmed.intent == VoiceIntent.approve
    assert approval_service.get(approval.id).status == ApprovalStatus.approved
    assert "token" in confirmed.text.lower()
    assert confirmed.sensitive_data_redacted is True


def test_confirmation_is_bound_to_original_user() -> None:
    approval = approval_service.request(
        ApprovalRequestCreate(
            action="release.deploy",
            requested_by="planner",
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason="Release candidate ready",
        )
    )
    first = voice_control_service.handle_transcript(request(f"Phoenix freigeben {approval.id}"))
    mobile_control_service.set_authorized_users({77, 88})
    with pytest.raises(VoiceControlError, match="nicht für diesen Benutzer"):
        voice_control_service.handle_transcript(request(f"Phoenix bestätigen {first.confirmation_id}", 88))


def test_telegram_voice_without_transcript_waits_for_stt_provider() -> None:
    reply = voice_control_service.handle_telegram_voice(
        TelegramVoiceRequest(
            telegram_user_id=77,
            chat_id=100,
            file_id="telegram-file-id",
            duration_seconds=8,
        )
    )
    assert reply.intent == VoiceIntent.unknown
    assert "Speech-to-Text" in reply.text
    assert voice_control_service.status().raw_audio_stored is False
    assert voice_control_service.status().automatic_merge is False
