// AURON chat: a dock above the status bar. The conversation lives in this browser
// (the backend is stateless) and goes whole to /v1/assistant/chat on every question.
(() => {
  const API = localStorage.getItem('auron_api') || (location.protocol === 'file:' ? 'http://localhost:8000' : '/api');
  const KEY = 'auron_chat';
  const KEEP = 30;  // turns sent along; older ones stay on screen only
  const dock = document.getElementById('chat');
  const log = document.getElementById('chatLog');
  const form = document.getElementById('chatForm');
  const input = document.getElementById('chatInput');
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const TAGS = /\[[a-zA-Z ]{2,24}\]\s*/g;  // [laughs] etc.: for the voice, not for the eyes
  const TOOL_NAMES = { trading_status: 'Trading', watchlist: 'Watchlist', instagram_status: 'Instagram', web_search: 'Web' };

  let turns = [];
  try { turns = JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { turns = []; }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(turns.slice(-100))); } catch { /* private window */ } };
  const lang = () => { try { return localStorage.getItem('auron_lang') || 'de'; } catch { return 'de'; } };

  function render() {
    log.innerHTML = turns.map((t) => `<div class="msg ${t.role}${t.error ? ' err' : ''}">${esc(t.content.replace(TAGS, ''))}`
      + `${t.tools?.length ? `<small>${[...new Set(t.tools)].map((n) => TOOL_NAMES[n] || n).join(' · ')}</small>` : ''}</div>`).join('')
      || '<div class="msg hint">Frag mich etwas – „Wie läuft Trading heute?“, „Was macht Gold?“, „Recherchier NVIDIA“.</div>';
    log.scrollTop = log.scrollHeight;
  }

  function open(on = true) {
    dock.classList.toggle('open', on);
    if (on) { render(); input.focus(); }
  }

  async function ask(text) {
    turns.push({ role: 'user', content: text });
    const thinking = { role: 'assistant', content: 'AURON denkt nach …', pending: true };
    turns.push(thinking); render();
    form.classList.add('busy');
    try {
      const messages = turns.filter((t) => !t.pending && !t.error).slice(-KEEP).map(({ role, content }) => ({ role, content }));
      while (messages.length && messages[0].role !== 'user') messages.shift();
      const r = await fetch(`${API}/v1/assistant/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages, lang: lang() }) });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${r.status}`);
      Object.assign(thinking, { content: data.text, tools: data.tools, pending: false });
      if (voiceOn()) say(data.text).catch((err) => console.warn('voice:', err.message));
    } catch (e) {
      Object.assign(thinking, { content: `Fehler: ${e.message}`, error: true, pending: false });
    }
    form.classList.remove('busy');
    save(); render();
  }

  // ---- voice -------------------------------------------------------------
  const pref = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
  const setPref = (k, v) => { try { localStorage.setItem(k, v); } catch { /* private window */ } };
  const voiceOn = () => pref('auron_voice_on', '1') === '1';
  const chosen = () => { try { return JSON.parse(pref('auron_voice2', '')) || null; } catch { return null; } };
  const DEFAULT_VOICE = { provider: 'elevenlabs', voice: 'JBFqnCBsd6RMkjVDRZzb', model: 'eleven_v4', name: 'George', accent: 'British accent' }  // Brano's pick, 2026-10-16;
  const player = new Audio();
  let lastUrl = '';

  async function say(text, v = chosen() || DEFAULT_VOICE) {
    const r = await fetch(`${API}/v1/assistant/speak`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, provider: v.provider, voice: v.voice, model: v.model, accent: v.accent ?? DEFAULT_VOICE.accent }) });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || `HTTP ${r.status}`); }
    if (lastUrl) URL.revokeObjectURL(lastUrl);
    player.src = lastUrl = URL.createObjectURL(await r.blob());
    await player.play();
  }

  const speakBtn = document.getElementById('chatSpeak');
  const paintSpeak = () => { speakBtn.textContent = voiceOn() ? '🔊' : '🔇'; speakBtn.title = voiceOn() ? 'Vorlesen an' : 'Vorlesen aus'; };
  speakBtn.addEventListener('click', () => { setPref('auron_voice_on', voiceOn() ? '0' : '1'); if (!voiceOn()) player.pause(); paintSpeak(); });
  paintSpeak();

  const SAMPLE = '[chuckles] Guten Abend, Sir. Gold steht ruhig, die Kopierer laufen, und Instagram wartet mal wieder auf Sie. Soll ich weitermachen?';
  async function showVoices() {
    open(true);
    log.innerHTML = '<div class="msg hint">Lade Stimmen …</div>';
    let v;
    try { v = await (await fetch(`${API}/v1/assistant/voices`)).json(); } catch (e) { log.innerHTML = `<div class="msg err">Fehler: ${esc(e.message)}</div>`; return; }
    const cur = chosen() || DEFAULT_VOICE;
    const block = (provider, p) => p.voices.map((x) => `<div class="vrow${cur.provider === provider && cur.voice === x.id ? ' on' : ''}">
        <div><b>${esc(x.name)}</b><small>${esc(x.desc)}</small></div>
        <div class="vbtns">${p.models.map((m) => `<button type="button" data-p="${provider}" data-v="${esc(x.id)}" data-m="${esc(m.id)}" data-n="${esc(x.name)}" title="${esc(m.name)}"
          class="${cur.voice === x.id && cur.model === m.id ? 'sel' : ''}">▶ ${esc(m.name.split(' ')[0])}</button>`).join('')}</div></div>`).join('');
    log.innerHTML = `<div class="voices">
      <label class="vsample">Probesatz<textarea id="vSample" rows="2">${esc(SAMPLE)}</textarea></label>
      <p class="vnote">▶ spielt die Probe. Die zuletzt gespielte wird AURONs Stimme. v3/v4 können lachen und seufzen.</p>
      <div class="vhead">ElevenLabs${p_ok(v.elevenlabs)}</div>${block('elevenlabs', v.elevenlabs)}
      <div class="vhead">OpenAI${p_ok(v.openai)}</div>${block('openai', v.openai)}
      <button type="button" class="vdone" id="vDone">Fertig</button></div>`;
  }
  const p_ok = (p) => (p.available ? '' : ' <small>– kein Schlüssel</small>');
  log.addEventListener('click', async (e) => {
    if (e.target.id === 'vDone') { render(); return; }
    const b = e.target.closest('.vbtns button');
    if (!b) return;
    const v = { provider: b.dataset.p, voice: b.dataset.v, model: b.dataset.m, name: b.dataset.n };
    const text = document.getElementById('vSample').value.trim() || SAMPLE;
    log.querySelectorAll('.vbtns button').forEach((x) => x.classList.remove('sel'));
    b.classList.add('sel', 'loading');
    try {
      await say(text, v);
      setPref('auron_voice2', JSON.stringify(v));
      log.querySelectorAll('.vrow').forEach((r) => r.classList.toggle('on', r.contains(b)));
    } catch (err) { b.title = `Fehler: ${err.message}`; b.classList.add('bad'); }
    b.classList.remove('loading');
  });
  document.getElementById('chatVoices').addEventListener('click', showVoices);

  // ---- listening: record, stop on silence, transcribe, ask ----------------
  const mic = document.getElementById('chatMic');
  let rec = null;
  async function listen() {
    if (rec) { rec.stop(); return; }                      // second click: stop now
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); }
    catch (e) { open(true); turns.push({ role: 'assistant', content: `Mikrofon nicht verfügbar: ${e.message}`, error: true }); render(); return; }
    player.pause();                                        // don't record AURON talking
    const chunks = [];
    rec = new MediaRecorder(stream);
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    // Silence detection: once he has spoken, 1.6 s of quiet ends the recording; 60 s at most.
    const ctx = new AudioContext(), an = ctx.createAnalyser();
    ctx.createMediaStreamSource(stream).connect(an);
    const buf = new Uint8Array(an.fftSize);
    let spoke = false, quietSince = performance.now();
    const started = performance.now();
    const tick = () => {
      if (!rec || rec.state !== 'recording') return;
      an.getByteTimeDomainData(buf);
      const level = Math.sqrt(buf.reduce((a, v) => a + (v - 128) ** 2, 0) / buf.length);
      const now = performance.now();
      if (level > 6) { spoke = true; quietSince = now; }
      if ((spoke && now - quietSince > 1600) || now - started > 60000 || (!spoke && now - started > 8000)) rec.stop();
      else requestAnimationFrame(tick);
    };
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop()); ctx.close();
      rec = null; mic.classList.remove('rec');
      if (!spoke || !chunks.length) return;
      const blob = new Blob(chunks, { type: chunks[0].type || 'audio/webm' });
      mic.classList.add('busy');
      try {
        const r = await fetch(`${API}/v1/assistant/listen?lang=${lang()}`, { method: 'POST', headers: { 'Content-Type': blob.type }, body: blob });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
        if (d.text) { open(true); ask(d.text); }
      } catch (e) { open(true); turns.push({ role: 'assistant', content: `Nicht verstanden: ${e.message}`, error: true }); render(); }
      mic.classList.remove('busy');
    };
    rec.start();
    mic.classList.add('rec');
    tick();
  }
  mic.addEventListener('click', listen);

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || form.classList.contains('busy')) return;
    input.value = '';
    open(true);
    ask(text);
  });
  input.addEventListener('focus', () => open(true));
  document.getElementById('chatClose').addEventListener('click', () => open(false));
  document.getElementById('chatClear').addEventListener('click', () => { turns = []; save(); render(); input.focus(); });
  document.getElementById('core')?.addEventListener('click', () => open(!dock.classList.contains('open')));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && dock.classList.contains('open')) open(false); });
})();
