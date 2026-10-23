// A laptop step that waits for Brano (backend/app/desk): a program file to open, or any step right after
// AURON read a mail or a web page. Asked here, on every open dashboard -- his click is the only way it runs;
// AURON has no way to approve it himself. The first screen that gets an answer wins.
(() => {
  const API_BASE = typeof API !== 'undefined' ? API : '/api';
  const asked = new Set();
  const WHAT = { open: 'öffnen', close: 'schließen', minimize: 'minimieren', maximize: 'maximieren', restore: 'wiederherstellen',
    focus: 'nach vorne holen', fullscreen: 'Vollbild', move_monitor: 'auf Monitor schieben', scroll: 'scrollen',
    windows: 'Fenster auflisten', monitors: 'Monitore auflisten' };
  async function poll() {
    if (document.hidden) return;
    let list;
    try { list = await (await fetch(`${API_BASE}/v1/desk/waiting`)).json(); } catch { return; }
    for (const c of list || []) {
      if (asked.has(c.id)) continue;
      asked.add(c.id);
      const a = c.args || {};
      const step = `${WHAT[c.action] || c.action}${a.target ? `: ${a.target}` : ''}${a.monitor ? ` → Monitor ${a.monitor}` : ''}`;
      const ok = confirm(`AURON möchte am Laptop:\n${step}\n\nGrund für die Rückfrage: ${c.reason}\n\nErlauben?`);
      try {
        await fetch(`${API_BASE}/v1/desk/${c.id}/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ok }) });
      } catch { /* another screen answered first */ }
    }
  }
  setInterval(poll, 1500);
})();
