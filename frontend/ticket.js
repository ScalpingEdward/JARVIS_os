// A trade AURON prepared (backend/app/copier_status/tickets.py): the card above the AURON ring shows it --
// symbol, side, lots, entry, stop, targets, risk -- with "Eröffnen" and "Verwerfen". It opens on this click or
// on Brano's own spoken or typed order to AURON; the server checks that order, not AURON.
(() => {
  const API_BASE = typeof API !== 'undefined' ? API : '/api';
  const fmtN = (v, d = 2) => (v == null ? '–' : Number(v).toLocaleString('de-DE', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const card = document.createElement('section');
  card.className = 'ticket'; card.hidden = true;
  document.body.append(card);
  let shown = null, sentAt = 0;

  function paint(t) {
    const dec = t.entry > 1000 ? 2 : t.entry > 10 ? 3 : 5;
    const legs = t.legs.map((l, i) => `<span>TP${t.legs.length > 1 ? i + 1 : ''} <b>${l.tp ? fmtN(l.tp, dec) : '–'}</b> · ${fmtN(l.lots)} Lots${t.rr[i] ? ` · ${fmtN(t.rr[i], 1)} R` : ''}</span>`).join('');
    const sent = t.status === 'sent';
    card.innerHTML = `<header><b class="${t.side}">${t.side.toUpperCase()} ${t.symbol}</b><small>${t.account}</small>
        <button type="button" class="tk-x" title="Verwerfen">✕</button></header>
      <div class="tk-grid"><span>Lots <b>${fmtN(t.lots)}</b></span><span>Einstieg <b>${fmtN(t.entry, dec)}</b></span>
        <span>SL <b>${t.sl ? fmtN(t.sl, dec) : '–'}</b></span>
        <span>Risiko <b>${fmtN(t.risk_money)} ${t.currency || ''}</b>${t.risk_pct != null ? ` (${fmtN(t.risk_pct)} %)` : ''}</span></div>
      <div class="tk-legs">${legs}</div>
      ${sent ? '<p class="tk-sent">An den Kopierer gesendet – er eröffnet in bis zu 20 s.</p>'
        : '<div class="tk-btns"><button type="button" class="tk-open">Eröffnen</button><small>oder sag „Eröffne jetzt“</small></div>'}`;
  }

  async function poll() {
    let d;
    try { d = await (await fetch(`${API_BASE}/v1/copier/tickets/active`)).json(); } catch { return; }
    const t = d.ticket;
    if (!t || t.status === 'cancelled' || t.status === 'expired' || (t.status === 'sent' && Date.now() - sentAt > 30000 && sentAt)) {
      card.hidden = true; shown = null; return;
    }
    if (t.status === 'sent' && !sentAt) sentAt = Date.now();
    if (t.status === 'ready') sentAt = 0;
    const key = JSON.stringify(t);
    if (key !== shown) { paint(t); shown = key; }
    card.hidden = false;
  }

  card.addEventListener('click', async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.classList.contains('tk-open')) {
      const t = JSON.parse(shown);
      if (!confirm(`${t.side.toUpperCase()} ${t.symbol} · ${t.lots} Lots · Risiko ${fmtN(t.risk_money)} ${t.currency || ''}\nKonto: ${t.account}\n\nJetzt zum Marktpreis eröffnen?`)) return;
      b.disabled = true;
      const r = await fetch(`${API_BASE}/v1/copier/tickets/open`, { method: 'POST' });
      if (!r.ok) alert((await r.json().catch(() => ({}))).detail || `Fehler ${r.status}`);
    }
    if (b.classList.contains('tk-x')) await fetch(`${API_BASE}/v1/copier/tickets/cancel`, { method: 'POST' });
    poll();
  });
  poll();
  setInterval(poll, 2000);
})();
