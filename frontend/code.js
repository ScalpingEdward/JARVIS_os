// Settings › Code: the code wishes AURON passed on to Claude Code (backend/app/code_tasks,
// tools/code_runner.py). Each shows what Claude Code changed and whether the checks passed;
// only "Freigeben" here puts it live -- AURON cannot. AURON also says when one is ready.
(() => {
  const API_BASE = typeof API !== 'undefined' ? API : '/api';
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const STATE = {
    queued: ['wartet auf den Runner', ''], running: ['Claude Code arbeitet …', 'busy'], ready: ['bereit zur Freigabe', 'ready'],
    failed: ['fehlgeschlagen', 'bad'], approved: ['freigegeben – wird übernommen', 'busy'], applying: ['wird übernommen …', 'busy'],
    applied: ['live', 'ok'], apply_failed: ['Übernehmen fehlgeschlagen', 'bad'], rejected: ['verworfen – wird gelöscht', ''],
    discarding: ['wird gelöscht', ''], discarded: ['verworfen', ''], revert_requested: ['wird zurückgenommen', 'busy'],
    reverting: ['wird zurückgenommen …', 'busy'], reverted: ['zurückgenommen', ''], revert_failed: ['Zurücknehmen fehlgeschlagen', 'bad'],
  };
  let tasks = [], box = null, seen = null;
  const open = new Set();

  async function claim(text) {
    try {
      const r = await fetch(`${API_BASE}/v1/assistant/announce-claim`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key: text }) });
      return r.ok ? (await r.json()).speak : true;
    } catch { return true; }
  }

  async function load() {
    try { tasks = await (await fetch(`${API_BASE}/v1/code/tasks`)).json(); } catch { return; }
    // AURON says it when a wish is ready, failed or live -- one voice across all screens (announce-claim)
    const now = new Map(tasks.map((t) => [t.id, t.status]));
    if (seen) {
      for (const t of tasks) {
        if (seen.get(t.id) === t.status) continue;
        const say = {
          ready: `Sir, die Code-Änderung ist bereit: ${t.text.slice(0, 80)}. Sie finden sie unter Einstellungen, Code.`,
          failed: 'Sir, die Code-Änderung hat nicht geklappt. Die Details stehen unter Einstellungen, Code.',
          applied: 'Sir, die Änderung ist jetzt live.',
        }[t.status];
        if (say) { window.AURON_voice?.note(say, { code: t.id }); claim(say).then((mine) => { if (mine) window.AURON_voice?.say(say); }); }
      }
    } else {
      // first look on this screen: a wish already waiting gets its message with buttons, once
      for (const t of tasks) {
        if ((t.status === 'ready' || t.status === 'apply_failed') && !window.AURON_voice?.hasCode(t.id)) {
          window.AURON_voice?.note(`Sir, eine Code-Änderung wartet auf Ihre Freigabe: ${t.text.slice(0, 120)}`, { code: t.id });
        }
      }
    }
    seen = now;
    window.AURON_voice?.refresh();
    if (box && box.isConnected) paint();
  }

  function paint() {
    if (!tasks.length) {
      box.innerHTML = '<p class="muted">Noch keine Code-Aufträge. Sag AURON, was im Dashboard anders sein soll – er gibt es an Claude Code, und du gibst es hier frei.</p>';
      return;
    }
    box.innerHTML = tasks.slice(0, 15).map((t) => {
      const [label, cls] = STATE[t.status] || [t.status, ''];
      const btns = t.status === 'ready' || t.status === 'apply_failed'
        ? `<button type="button" class="go" data-a="approve" data-id="${t.id}">✅ ${t.status === 'ready' ? 'Freigeben' : 'Nochmal übernehmen'}</button><button type="button" data-a="reject" data-id="${t.id}">Verwerfen</button>`
        : t.status === 'applied' ? `<button type="button" data-a="revert" data-id="${t.id}">↩ Rückgängig</button>` : '';
      const more = open.has(t.id);
      const when = new Date(t.created_at).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
      return `<article class="ct ${cls}">
        <div class="ct-top"><b>${esc(t.text)}</b><span class="ct-state">${label}</span></div>
        ${t.summary ? `<p class="ct-sum">${esc(t.summary)}</p>` : ''}
        ${t.error ? `<p class="ct-err">${esc(t.error)}</p>` : ''}
        ${t.tests ? `<pre class="ct-tests">${esc(t.tests)}</pre>` : ''}
        ${t.diff ? `<button type="button" class="ct-more" data-more="${t.id}">${more ? 'Änderungen ausblenden' : 'Änderungen ansehen'}</button>` : ''}
        ${more && t.diff ? `<pre class="ct-diff">${esc(t.diff)}</pre>` : ''}
        ${btns ? `<div class="ct-btns">${btns}</div>` : ''}
        <small class="muted">${when}</small>
      </article>`;
    }).join('');
  }

  async function act(e) {
    const m = e.target.closest('[data-more]');
    if (m) { if (open.has(m.dataset.more)) open.delete(m.dataset.more); else open.add(m.dataset.more); paint(); return; }
    const b = e.target.closest('button[data-a]');
    if (!b) return;
    const ask = {
      approve: 'Diese Änderung jetzt live nehmen? AURON baut neu und startet das Fenster neu.',
      reject: 'Diese Änderung verwerfen?',
      revert: 'Diese Änderung zurücknehmen? AURON baut neu.',
    }[b.dataset.a];
    if (!confirm(ask)) return;
    b.disabled = true;
    try {
      const r = await fetch(`${API_BASE}/v1/code/tasks/${b.dataset.id}/${b.dataset.a}`, { method: 'POST' });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.status);
    } catch (err) { alert(`Fehler: ${err.message}`); }
    load();
  }

  window.AURON_code = {
    editor(el) { box = el; box.addEventListener('click', act); paint(); load(); },
    // under the chat message about a wish: what can be done with it right now
    buttons(id) {
      const t = tasks.find((x) => x.id === id);
      if (!t) return '';
      const [label] = STATE[t.status] || [t.status];
      const b = t.status === 'ready' || t.status === 'apply_failed'
        ? `<button type="button" class="go" data-a="approve" data-id="${id}">✅ ${t.status === 'ready' ? 'Freigeben' : 'Nochmal übernehmen'}</button><button type="button" data-a="reject" data-id="${id}">Verwerfen</button>`
        : t.status === 'applied' ? `<button type="button" data-a="revert" data-id="${id}">↩ Rückgängig</button>` : '';
      return `<div class="ct-btns msg-code">${b}<button type="button" data-details="${id}">Details</button><span class="muted">${label}</span></div>`;
    },
  };
  // the buttons in the chat
  document.getElementById('chatLog')?.addEventListener('click', (e) => {
    if (e.target.closest('[data-details]')) { window.AURON_settings?.open('code'); return; }
    if (e.target.closest('.msg-code button[data-a]')) act(e);
  });
  load();
  setInterval(load, 5000);
})();
