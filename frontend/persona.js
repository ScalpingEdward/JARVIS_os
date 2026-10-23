// Einstellungen > AURON (Brano, 2026-10-22): his language and how he addresses Brano (2026-10-23), how much
// and which humor, and everything he taught AURON
// ("merk dir ...") -- visible, deletable, and new entries by hand. backend/app/assistant/persona.py
(() => {
  const API_BASE = typeof API !== 'undefined' ? API : '/api';
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const NAMES = { trocken: 'Trocken', sarkastisch: 'Sarkastisch', verspielt: 'Verspielt', wortwitz: 'Wortwitz', selbstironisch: 'Selbstironisch' };
  const req = async (method, path, body) => {
    const r = await fetch(`${API_BASE}/v1/assistant/persona${path}`, { method, headers: { 'Content-Type': 'application/json' }, body: body && JSON.stringify(body) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
    return d;
  };

  const a0 = (d) => d.address || {};
  async function editor(el) {
    let d;
    try { d = await req('GET', ''); } catch (e) { el.innerHTML = `<p class="th-text">Nicht erreichbar: ${esc(e.message)}</p>`; return; }
    const paint = () => {
      const a = d.address || { style: 'sir' };
      el.innerHTML = `<section class="th-sec"><h4>Sprache</h4>
          <select class="ps-lang" data-p="language">${Object.entries(d.languages || {}).map(([k, n]) =>
            `<option value="${k}" ${k === d.language ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select>
          <p class="th-text">Darin spricht, hört und antwortet AURON – überall. Auch per Zuruf: „Sprich Tschechisch“.</p>
          <span class="th-label">Anrede</span><div class="seg ps-addr">
            <button type="button" data-p="address" data-v="sir" class="${a.style === 'sir' ? 'on' : ''}">„Sir“ · Sie</button>
            <button type="button" data-p="address" data-v="name" class="${a.style === 'name' ? 'on' : ''}">„Brano“ · Du</button>
            <button type="button" data-p="address" data-v="custom" class="${a.style === 'custom' ? 'on' : ''}">Eigene</button></div>
          ${a.style === 'custom' ? `<p class="th-text">Jetzt: ${esc(a.text)}</p>` : ''}</section>
        <section class="th-sec"><h4>Humor</h4>
          <span class="th-label">Stärke <b data-out>${d.humor.level} / 10</b></span>
          <input type="range" min="0" max="10" step="1" data-p="level" value="${d.humor.level}" />
          <span class="th-label">Art</span><div class="seg ps-styles">${Object.keys(d.styles).map((k) =>
            `<button type="button" data-p="style" data-v="${k}" class="${k === d.humor.style ? 'on' : ''}" title="${esc(d.styles[k])}">${NAMES[k] || k}</button>`).join('')}</div>
          <p class="th-text">${esc(d.styles[d.humor.style])}</p></section>
        <section class="th-sec"><h4>Was AURON sich merkt</h4>
          <p class="th-text">AURON merkt sich von selbst, was du über dich erzählst; dazu „merk dir …“ oder hier hineinschreiben. Alles gilt, bis du es löschst – Momentanes („bin auf Arbeit“) läuft von selbst ab.</p>
          <form class="ps-add"><input maxlength="300" placeholder="z. B. Bei Verlusten keine Witze." /><button type="submit">Merken</button></form>
          <div class="ps-mem">${d.memories.map((m) => `<div class="${m.by === 'auron' ? 'auto' : ''}"><span>${esc(m.text)}<small>${esc(m.at)} · ${m.by === 'auron' ? 'von AURON gemerkt' : 'von dir'}${m.kind === 'now' && m.until ? ` · gilt bis ${new Date(m.until * 1000).toLocaleString('de-DE', { weekday: 'short', hour: '2-digit', minute: '2-digit' })}` : ''}</small></span>
            <button type="button" data-p="forget" data-v="${m.id}" title="Vergessen">✕</button></div>`).join('') || '<p class="th-text">Noch nichts.</p>'}</div></section>`;
    };
    paint();
    el.onclick = async (e) => {
      const b = e.target.closest('button[data-p]');
      if (!b) return;
      try {
        if (b.dataset.p === 'style') { d.humor = await req('PUT', '/humor', { style: b.dataset.v }); }
        if (b.dataset.p === 'address') {
          const text = b.dataset.v === 'custom' ? prompt('Wie soll AURON dich ansprechen? z. B. „Boss, mit Du“', a0(d).text || '') : '';
          if (b.dataset.v === 'custom' && !text) return;
          Object.assign(d, await req('PUT', '/language', { address: b.dataset.v, text: text || '' }));
        }
        if (b.dataset.p === 'forget') { await req('DELETE', `/memory/${b.dataset.v}`); d.memories = d.memories.filter((m) => String(m.id) !== b.dataset.v); }
        paint();
      } catch (err) { alert(`Fehler: ${err.message}`); }
    };
    el.oninput = (e) => { if (e.target.dataset.p === 'level') el.querySelector('[data-out]').textContent = `${e.target.value} / 10`; };
    el.onchange = async (e) => {
      if (e.target.dataset.p === 'language') {
        try { Object.assign(d, await req('PUT', '/language', { language: e.target.value })); paint(); } catch (err) { alert(`Fehler: ${err.message}`); }
        return;
      }
      if (e.target.dataset.p !== 'level') return;
      try { d.humor = await req('PUT', '/humor', { level: Number(e.target.value) }); } catch (err) { alert(`Fehler: ${err.message}`); }
    };
    el.onsubmit = async (e) => {
      e.preventDefault();
      const i = el.querySelector('.ps-add input'), text = i.value.trim();
      if (!text) return;
      try { const m = await req('POST', '/memory', { text }); if (!m.already) d.memories.push(m); paint(); }
      catch (err) { alert(`Fehler: ${err.message}`); }
    };
  }
  window.AURON_persona = { editor };
})();
