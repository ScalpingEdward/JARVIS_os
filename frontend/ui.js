// AURON shows things on the dashboard on Brano's word -- "öffne Trading", "zeig mir den Chart von NINJA",
// "mach zu" (backend/app/dashboard_layout/ui.py). Asked every 1.5 s; a dashboard that starts takes the
// current command number first, so nothing old is replayed.
(() => {
  const API_BASE = typeof API !== 'undefined' ? API : '/api';
  let after = null;
  async function poll() {
    let d;
    try { d = await (await fetch(`${API_BASE}/v1/dashboard/ui?after=${after ?? 0}`)).json(); } catch { return; }
    if (after === null) { after = d.last; return; }
    for (const c of d.commands) {
      after = Math.max(after, c.seq);
      if (c.do === 'open_view') { window.AURON_chart?.close(); window.AURON_view?.open(c.view); }
      else if (c.do === 'close') { window.AURON_chart?.close(); window.AURON_view?.close(); }
      else if (c.do === 'show_chart') { window.AURON_view?.close(); window.AURON_chart?.open(c.ticket, c.copier, c.tf); }
      else if (c.do === 'show_symbol') { window.AURON_view?.close(); window.AURON_chart?.symbol(c.symbol, c.copier, c.tf); }
    }
  }
  poll();
  setInterval(poll, 1500);
})();
