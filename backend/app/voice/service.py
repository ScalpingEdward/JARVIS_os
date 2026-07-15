from __future__ import annotations

import os
from uuid import UUID

from app.mobile.models import TelegramUpdate
from app.mobile.service import MobileControlError, mobile_control_service

from .models import (
    TelegramVoiceRequest,
    VoiceConfirmation,
    VoiceIntent,
    VoiceReply,
    VoiceSettings,
    VoiceStatus,
    VoiceTranscriptRequest,
)


class VoiceControlError(ValueError):
    pass


class VoiceControlService:
    """Maps transcripts to existing mobile commands with explicit confirmation gates."""

    def __init__(self) -> None:
        self._settings = self._settings_from_env()
        self._pending: dict[UUID, VoiceConfirmation] = {}

    def reset(self) -> None:
        self._settings = self._settings_from_env()
        self._pending.clear()

    def configure(self, settings: VoiceSettings) -> VoiceSettings:
        self._settings = settings
        return self._settings.model_copy(deep=True)

    def settings(self) -> VoiceSettings:
        return self._settings.model_copy(deep=True)

    def status(self) -> VoiceStatus:
        return VoiceStatus(settings=self.settings(), pending_confirmations=len(self._pending))

    def handle_transcript(self, payload: VoiceTranscriptRequest) -> VoiceReply:
        transcript = payload.transcript.strip()
        command_text = self._strip_wake_name(transcript)
        intent, argument = self._parse(command_text)
        if intent == VoiceIntent.unknown:
            return self._reply(intent, "Befehl nicht erkannt. Sage Status, Tagesplan, Pause, Weiter oder Freigaben.")
        if intent in {VoiceIntent.approve, VoiceIntent.reject} and self._settings.critical_confirmation_required:
            if not argument:
                raise VoiceControlError("Für Freigabe oder Ablehnung ist eine Approval-ID erforderlich")
            confirmation = VoiceConfirmation(user_id=payload.telegram_user_id, intent=intent, argument=argument)
            self._pending[confirmation.id] = confirmation
            return self._reply(
                intent,
                f"Kritische Aktion erkannt. Bestätige mit: {self._settings.wake_name} bestätigen {confirmation.id}",
                requires_confirmation=True,
                confirmation_id=confirmation.id,
            )
        if intent == VoiceIntent.confirm:
            return self._confirm(payload, argument)
        if intent == VoiceIntent.cancel:
            return self._cancel(payload, argument)
        command = self._to_mobile_command(intent, argument)
        return self._execute_mobile(payload, intent, command)

    def handle_telegram_voice(self, payload: TelegramVoiceRequest) -> VoiceReply:
        if payload.transcript is None:
            return self._reply(
                VoiceIntent.unknown,
                "Sprachnachricht empfangen. Ein Speech-to-Text-Provider muss konfiguriert werden, bevor Audio transkribiert wird.",
            )
        return self.handle_transcript(
            VoiceTranscriptRequest(
                telegram_user_id=payload.telegram_user_id,
                chat_id=payload.chat_id,
                transcript=payload.transcript,
            )
        )

    def _confirm(self, payload: VoiceTranscriptRequest, argument: str | None) -> VoiceReply:
        confirmation_id = self._uuid(argument, "Bestätigungs-ID fehlt oder ist ungültig")
        confirmation = self._pending.get(confirmation_id)
        if confirmation is None or confirmation.user_id != payload.telegram_user_id:
            raise VoiceControlError("Bestätigung nicht gefunden oder nicht für diesen Benutzer")
        command = self._to_mobile_command(confirmation.intent, confirmation.argument)
        result = self._execute_mobile(payload, confirmation.intent, command)
        self._pending.pop(confirmation_id, None)
        return result

    def _cancel(self, payload: VoiceTranscriptRequest, argument: str | None) -> VoiceReply:
        confirmation_id = self._uuid(argument, "Bestätigungs-ID fehlt oder ist ungültig")
        confirmation = self._pending.get(confirmation_id)
        if confirmation is None or confirmation.user_id != payload.telegram_user_id:
            raise VoiceControlError("Bestätigung nicht gefunden oder nicht für diesen Benutzer")
        self._pending.pop(confirmation_id, None)
        return self._reply(VoiceIntent.cancel, "Kritische Aktion wurde abgebrochen.")

    def _execute_mobile(self, payload: VoiceTranscriptRequest, intent: VoiceIntent, command: str) -> VoiceReply:
        try:
            mobile_reply = mobile_control_service.handle(
                TelegramUpdate(
                    telegram_user_id=payload.telegram_user_id,
                    chat_id=payload.chat_id,
                    text=command,
                )
            )
        except MobileControlError as exc:
            raise VoiceControlError(str(exc)) from exc
        return self._reply(intent, mobile_reply.text)

    def _strip_wake_name(self, transcript: str) -> str:
        normalized = transcript.strip()
        wake = self._settings.wake_name.strip()
        if normalized.lower().startswith(wake.lower()):
            return normalized[len(wake):].lstrip(" ,:-")
        if self._settings.require_wake_name:
            raise VoiceControlError(f"Wake-Name '{wake}' fehlt")
        return normalized

    @staticmethod
    def _parse(text: str) -> tuple[VoiceIntent, str | None]:
        cleaned = text.strip().lower()
        mappings = {
            "status": VoiceIntent.status,
            "stand": VoiceIntent.status,
            "tagesplan": VoiceIntent.today,
            "heute": VoiceIntent.today,
            "freigaben": VoiceIntent.approvals,
            "approvals": VoiceIntent.approvals,
            "pause": VoiceIntent.pause,
            "stopp": VoiceIntent.pause,
            "weiter": VoiceIntent.resume,
            "fortsetzen": VoiceIntent.resume,
            "resume": VoiceIntent.resume,
            "freigeben": VoiceIntent.approve,
            "approve": VoiceIntent.approve,
            "ablehnen": VoiceIntent.reject,
            "reject": VoiceIntent.reject,
            "bestätigen": VoiceIntent.confirm,
            "bestaetigen": VoiceIntent.confirm,
            "confirm": VoiceIntent.confirm,
            "abbrechen": VoiceIntent.cancel,
            "cancel": VoiceIntent.cancel,
        }
        parts = cleaned.split(maxsplit=1)
        return mappings.get(parts[0], VoiceIntent.unknown), parts[1] if len(parts) == 2 else None

    @staticmethod
    def _to_mobile_command(intent: VoiceIntent, argument: str | None) -> str:
        mapping = {
            VoiceIntent.status: "/status",
            VoiceIntent.today: "/today",
            VoiceIntent.approvals: "/approvals",
            VoiceIntent.pause: "/pause",
            VoiceIntent.resume: "/resume",
            VoiceIntent.approve: "/approve",
            VoiceIntent.reject: "/reject",
        }
        if intent not in mapping:
            raise VoiceControlError("Intent kann nicht ausgeführt werden")
        return f"{mapping[intent]} {argument}".strip()

    def _reply(
        self,
        intent: VoiceIntent,
        text: str,
        *,
        requires_confirmation: bool = False,
        confirmation_id: UUID | None = None,
    ) -> VoiceReply:
        return VoiceReply(
            ok=True,
            assistant_name=self._settings.assistant_name,
            text=text,
            intent=intent,
            requires_confirmation=requires_confirmation,
            confirmation_id=confirmation_id,
            speak_text=text,
            sensitive_data_redacted=True,
        )

    @staticmethod
    def _uuid(value: str | None, message: str) -> UUID:
        try:
            return UUID(value or "")
        except ValueError as exc:
            raise VoiceControlError(message) from exc

    @staticmethod
    def _settings_from_env() -> VoiceSettings:
        name = os.getenv("ASSISTANT_NAME", "PHOENIX")
        return VoiceSettings(
            assistant_name=name,
            wake_name=os.getenv("ASSISTANT_WAKE_NAME", name.lower()),
            language=os.getenv("VOICE_LANGUAGE", "de-DE"),
            speech_to_text_provider=os.getenv("VOICE_STT_PROVIDER", "provider-not-configured"),
            text_to_speech_provider=os.getenv("VOICE_TTS_PROVIDER", "provider-not-configured"),
        )


voice_control_service = VoiceControlService()
