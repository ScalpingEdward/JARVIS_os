# PHOENIX v21.227 — Demo 1 Voice Adapter Contract, STT/TTS Provider Binding & Fallback Governance

## Purpose
Turn Demo 1's voice-first intent into an explicit provider-binding contract connected to the existing PHOENIX voice-control configuration.

## Added
- canonical STT/TTS provider names are read from `voice_control_service.settings()`;
- provider binding is exposed through a dedicated Demo 1 voice status endpoint;
- deterministic voice/text/silent channel resolution;
- healthy STT + TTS produces voice-to-voice readiness;
- unavailable or unhealthy STT falls back to text input when available;
- unavailable or unhealthy TTS falls back to text output when available;
- lack of both voice transport and text fallback fails closed;
- Risk Brain hard block forces silent/blocked state;
- voice transport never changes the approval boundary or enables autonomous high-risk execution.

## API
- `GET /phoenix/demo1/v21.227/voice/status`
- `POST /phoenix/demo1/v21.227/voice/resolve`

## Existing voice subsystem binding
The existing `/v1/voice` subsystem already owns wake-name handling, short-lived conversation context, confirmation gates, history, Telegram voice intake and provider configuration. v21.227 does not duplicate that logic; it binds Demo 1 to the same canonical STT/TTS settings and governs fallback behavior around that subsystem.

The default configuration currently supports browser/client speech providers (`browser-web-speech` and `browser-speech-synthesis`). Actual microphone capture and audio playback remain responsibilities of the browser/operator client; the backend now exposes a truthful provider contract and fallback decision instead of treating voice availability as a simple boolean.

## Readiness impact
After v21.227, the Demo 1 readiness contract may report `voice_adapter_bound = true`. Remaining integration priorities are:
- persistent approval inbox;
- memory-provider binding;
- operator UI/dashboard;
- concrete tool adapters.

## Safety boundary
`autonomous_high_risk_execution_enabled = false`. Voice input is an interaction transport, not an authorization bypass.

## Next
v21.228 — Demo 1 Persistent Approval Inbox & Deferred Request Recovery Governance.
