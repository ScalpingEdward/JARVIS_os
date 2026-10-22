// Talking with AURON live (the AURON ring in the chat bar): ElevenLabs' agent listens all the time, notices pauses and can
// be interrupted; AURON answers in George's voice (backend/app/assistant/live.py). His tools run here:
// the agent asks this page, the page asks AURON's API -- the same tools as in the chat. What is said
// on both sides lands in the chat. Tap the ring again to end. chat.js decides when the ring talks live:
// window.AURON_live.start(quiet) answers whether the talk began.
(() => {
  const API_BASE = typeof API !== 'undefined' ? API : '/api';
  const SDK = 'https://cdn.jsdelivr.net/npm/@elevenlabs/client@1.28.0/+esm';
  const btn = document.getElementById('chatRing');
  if (!btn) return;
  let conv = null, starting = false;

  const IDLE = btn.title;
  const state = (s, title) => { btn.dataset.state = s; btn.title = title; };

  async function toolsFor() {
    // every tool of AURON's, run by his API; the agent knows them by name (live.py client_tools)
    const names = await (await fetch(`${API_BASE}/v1/assistant/live/tools`)).json().catch(() => []);
    return Object.fromEntries((names || []).map((name) => [name, async (args) => {
      const r = await fetch(`${API_BASE}/v1/assistant/live/tool`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, args: args || {} }) });
      return r.ok ? (await r.json()).result : `Fehler ${r.status}`;
    }]));
  }

  async function start(quiet = false) {
    if (starting) return false;
    starting = true; state('wait', 'Verbinde …');
    window.AURON_voice?.hush?.();                       // the chat's own voice stops
    try {
      const r = await fetch(`${API_BASE}/v1/assistant/live/session`, { method: 'POST' });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      const [{ Conversation }, clientTools] = await Promise.all([import(SDK), toolsFor()]);
      await navigator.mediaDevices.getUserMedia({ audio: true });
      conv = await Conversation.startSession({
        signedUrl: d.signed_url,
        clientTools,
        onConnect: () => state('on', 'Live – AURON hört zu. Antippen beendet das Gespräch.'),
        onDisconnect: () => { conv = null; state('off', IDLE); },
        onModeChange: ({ mode }) => { btn.dataset.mode = mode; },     // speaking / listening
        onMessage: ({ message, source }) => { if (message) window.AURON_voice?.live(source === 'user' ? 'user' : 'assistant', message); },
        onError: (e) => window.AURON_voice?.live('assistant', `Live-Fehler: ${e?.message || e}`),
      });
    } catch (e) {
      conv = null; state('off', IDLE);
      if (!quiet) window.AURON_voice?.live('assistant', `Live-Gespräch geht gerade nicht: ${e.message}`);
      starting = false;
      return false;
    }
    starting = false;
    return true;
  }

  async function stop() {
    const c = conv; conv = null;
    state('off', IDLE);
    try { await c?.endSession(); } catch { /* already gone */ }
  }

  window.AURON_live = { start, stop, active: () => !!conv || starting };
})();
