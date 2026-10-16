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
  const TOOL_NAMES = { trading_status: 'Trading', watchlist: 'Watchlist', instagram_status: 'Instagram', web_search: 'Web' };

  let turns = [];
  try { turns = JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { turns = []; }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(turns.slice(-100))); } catch { /* private window */ } };
  const lang = () => { try { return localStorage.getItem('auron_lang') || 'de'; } catch { return 'de'; } };

  function render() {
    log.innerHTML = turns.map((t) => `<div class="msg ${t.role}${t.error ? ' err' : ''}">${esc(t.content)}`
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
      document.dispatchEvent(new CustomEvent('auron:reply', { detail: data }));  // the voice hooks in here later
    } catch (e) {
      Object.assign(thinking, { content: `Fehler: ${e.message}`, error: true, pending: false });
    }
    form.classList.remove('busy');
    save(); render();
  }

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
