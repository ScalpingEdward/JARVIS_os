from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.mobile.models import TelegramUpdate
from app.mobile.service import MobileControlError, mobile_control_service

from .models import (
    TelegramVoiceRequest,
    VoiceConfirmation,
    VoiceHistory,
    VoiceIntent,
    VoiceReply,
    VoiceSettings,
    VoiceStatus,
    VoiceTranscriptRequest,
    VoiceTurn,
)


class VoiceControlError(ValueError):
    pass


class VoiceControlService:
    """Wake-word voice control with short-lived context and explicit safety gates."""

    def __init__(self) -> None:
        self._settings = self._settings_from_env()
        self._pending: dict[UUID, VoiceConfirmation] = {}
        self._sessions: dict[str, datetime] = {}
        self._history: dict[str, list[VoiceTurn]] = defaultdict(list)

    def reset(self) -> None:
        self._settings = self._settings_from_env()
        self._pending.clear()
        self._sessions.clear()
        self._history.clear()

    def configure(self, settings: VoiceSettings) -> VoiceSettings:
        self._settings = settings
        return self.settings()

    def settings(self) -> VoiceSettings:
        return self._settings.model_copy(deep=True)

    def status(self) -> VoiceStatus:
        self._expire_sessions()
        return VoiceStatus(
            settings=self.settings(),
            pending_confirmations=len(self._pending),
            active_sessions=len(self._sessions),
        )

    def history(self, session_id: str = "browser", limit: int = 20) -> VoiceHistory:
        items = self._history.get(session_id, [])[-limit:]
        return VoiceHistory(items=items, count=len(items))

    def handle_transcript(self, payload: VoiceTranscriptRequest) -> VoiceReply:
        self._expire_sessions()
        transcript = payload.transcript.strip()
        wake_only = transcript.lower().strip(" ,.!?:-") == self._settings.wake_name.lower()
        has_wake = transcript.lower().startswith(self._settings.wake_name.lower())
        session_active = payload.session_id in self._sessions

        if wake_only:
            self._activate(payload.session_id)
            return self._record(payload, self._reply(VoiceIntent.wake, self._settings.wake_reply, session_active=True))

        if has_wake:
            self._activate(payload.session_id)
            command_text = self._strip_wake_name(transcript)
        elif session_active:
            command_text = transcript
            self._activate(payload.session_id)
        elif self._settings.require_wake_name:
            raise VoiceControlError(f"Wake-Name '{self._settings.wake_name}' fehlt")
        else:
            command_text = transcript

        intent, argument = self._parse(command_text)
        if intent == VoiceIntent.unknown:
            return self._record(payload, self._reply(
                intent,
                "Befehl nicht erkannt. Sage Status, Tagesbriefing, Freigaben oder analysiere einen Markt.",
                session_active=True,
            ))

        if intent == VoiceIntent.market:
            symbol = (argument or "XAUUSD").upper()
            return self._record(payload, self._reply(
                intent,
                f"Ich öffne die aktuelle Analyse für {symbol}, {self._settings.owner_salutation}.",
                ui_action="focus_market",
                ui_target=symbol,
                session_active=True,
            ))

        if intent == VoiceIntent.briefing:
            return self._record(payload, self._reply(
                intent,
                f"Ich öffne dein Executive Briefing, {self._settings.owner_salutation}.",
                ui_action="open_briefing",
                ui_target="personal-ceo",
                session_active=True,
            ))

        if intent == VoiceIntent.approvals:
            return self._record(payload, self._reply(
                intent,
                "Ich öffne die ausstehenden Freigaben. Es wird nichts automatisch bestätigt.",
                ui_action="open_approvals",
                ui_target="approval-center",
                session_active=True,
            ))

        if intent in {VoiceIntent.approve, VoiceIntent.reject} and self._settings.critical_confirmation_required:
            if not argument:
                raise VoiceControlError("Für Freigabe oder Ablehnung ist eine Approval-ID erforderlich")
            confirmation = VoiceConfirmation(user_id=payload.telegram_user_id, intent=intent, argument=argument)
            self._pending[confirmation.id] = confirmation
            return self._record(payload, self._reply(
                intent,
                f"Kritische Aktion erkannt. Bestätige ausdrücklich mit: {self._settings.wake_name} bestätigen {confirmation.id}",
                requires_confirmation=True,
                confirmation_id=confirmation.id,
                session_active=True,
            ))

        if intent == VoiceIntent.confirm:
            return self._record(payload, self._confirm(payload, argument))
        if intent == VoiceIntent.cancel:
            return self._record(payload, self._cancel(payload, argument))

        command = self._to_mobile_command(intent, argument)
        return self._record(payload, self._execute_mobile(payload, intent, command))

    def handle_telegram_voice(self, payload: TelegramVoiceRequest) -> VoiceReply:
        if payload.transcript is None:
            return self._reply(
                VoiceIntent.unknown,
                "Sprachnachricht empfangen. Ein Speech-to-Text-Provider muss konfiguriert werden.",
            )
        return self.handle_transcript(VoiceTranscriptRequest(
            telegram_user_id=payload.telegram_user_id,
            chat_id=payload.chat_id,
            transcript=payload.transcript,
            session_id=f"telegram:{payload.telegram_user_id}:{payload.chat_id}",
            source="telegram",
        ))

    def _activate(self, session_id: str) -> None:
        self._sessions[session_id] = datetime.now(timezone.utc) + timedelta(seconds=self._settings.conversation_timeout_seconds)

    def _expire_sessions(self) -> None:
        now = datetime.now(timezone.utc)
        self._sessions = {key: expiry for key, expiry in self._sessions.items() if expiry > now}

    def _record(self, payload: VoiceTranscriptRequest, reply: VoiceReply) -> VoiceReply:
        self._history[payload.session_id].append(VoiceTurn(
            session_id=payload.session_id,
            transcript=payload.transcript,
            response=reply.text,
            intent=reply.intent,
        ))
        self._history[payload.session_id] = self._history[payload.session_id][-50:]
        return reply

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
        return self._reply(VoiceIntent.cancel, "Kritische Aktion wurde abgebrochen.", session_active=True)

    def _execute_mobile(self, payload: VoiceTranscriptRequest, intent: VoiceIntent, command: str) -> VoiceReply:
        try:
            mobile_reply = mobile_control_service.handle(TelegramUpdate(
                telegram_user_id=payload.telegram_user_id,
                chat_id=payload.chat_id,
                text=command,
            ))
        except MobileControlError as exc:
            raise VoiceControlError(str(exc)) from exc
        return self._reply(intent, mobile_reply.text, session_active=True)

    def _strip_wake_name(self, transcript: str) -> str:
        wake = self._settings.wake_name.strip()
        return transcript[len(wake):].lstrip(" ,:-")

    @staticmethod
    def _parse(text: str) -> tuple[VoiceIntent, str | None]:
        cleaned = text.strip().lower()
        if not cleaned:
            return VoiceIntent.wake, None
        phrases = {
            "wie ist": VoiceIntent.market,
            "zeige mir": VoiceIntent.market,
            "analysiere": VoiceIntent.market,
            "markt": VoiceIntent.market,
            "gold": VoiceIntent.market,
            "briefing": VoiceIntent.briefing,
            "executive briefing": VoiceIntent.briefing,
            "was ist heute wichtig": VoiceIntent.briefing,
        }
        for prefix, intent in phrases.items():
            if cleaned.startswith(prefix):
                argument = cleaned[len(prefix):].strip() or ("XAUUSD" if prefix == "gold" else None)
                return intent, argument
        mappings = {
            "status": VoiceIntent.status, "stand": VoiceIntent.status,
            "tagesplan": VoiceIntent.today, "heute": VoiceIntent.today,
            "freigaben": VoiceIntent.approvals, "approvals": VoiceIntent.approvals,
            "pause": VoiceIntent.pause, "stopp": VoiceIntent.pause,
            "weiter": VoiceIntent.resume, "fortsetzen": VoiceIntent.resume, "resume": VoiceIntent.resume,
            "freigeben": VoiceIntent.approve, "approve": VoiceIntent.approve,
            "ablehnen": VoiceIntent.reject, "reject": VoiceIntent.reject,
            "bestätigen": VoiceIntent.confirm, "bestaetigen": VoiceIntent.confirm, "confirm": VoiceIntent.confirm,
            "abbrechen": VoiceIntent.cancel, "cancel": VoiceIntent.cancel,
        }
        parts = cleaned.split(maxsplit=1)
        return mappings.get(parts[0], VoiceIntent.unknown), parts[1] if len(parts) == 2 else None

    @staticmethod
    def _to_mobile_command(intent: VoiceIntent, argument: str | None) -> str:
        mapping = {
            VoiceIntent.status: "/status", VoiceIntent.today: "/today",
            VoiceIntent.pause: "/pause", VoiceIntent.resume: "/resume",
            VoiceIntent.approve: "/approve", VoiceIntent.reject: "/reject",
        }
        if intent not in mapping:
            raise VoiceControlError("Intent kann nicht ausgeführt werden")
        return f"{mapping[intent]} {argument or ''}".strip()

    def _reply(self, intent: VoiceIntent, text: str, *, requires_confirmation: bool = False,
               confirmation_id: UUID | None = None, ui_action: str | None = None,
               ui_target: str | None = None, session_active: bool = False) -> VoiceReply:
        return VoiceReply(
            ok=True, assistant_name=self._settings.assistant_name, text=text, intent=intent,
            requires_confirmation=requires_confirmation, confirmation_id=confirmation_id,
            speak_text=text, ui_action=ui_action, ui_target=ui_target,
            session_active=session_active, sensitive_data_redacted=True,
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
        owner = os.getenv("OWNER_SALUTATION", "MASTER Brano")
        return VoiceSettings(
            assistant_name=name,
            wake_name=os.getenv("ASSISTANT_WAKE_NAME", name.lower()),
            owner_salutation=owner,
            wake_reply=os.getenv("VOICE_WAKE_REPLY", f"Yes, {owner}?"),
            language=os.getenv("VOICE_LANGUAGE", "de-DE"),
            speech_to_text_provider=os.getenv("VOICE_STT_PROVIDER", "browser-web-speech"),
            text_to_speech_provider=os.getenv("VOICE_TTS_PROVIDER", "browser-speech-synthesis"),
        )


voice_control_service = VoiceControlService()
