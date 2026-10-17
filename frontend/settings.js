// Settings in the bottom bar: the colour AURON speaks in and the glass of the cards.
// Kept in this browser (localStorage); the dashboard looks the same after a reload.
(() => {
  const KEY = 'auron_theme';
  const ACCENTS = [['#4fd8ff', 'Cyan'], ['#f5b84a', 'Gold'], ['#ff7eb6', 'Rosa'], ['#3ddc97', 'Grün'], ['#b88cff', 'Lila'], ['#f2f4f8', 'Weiß']];
  const TINTS = [['#96c8ff', 'Eisblau'], ['#ffd28c', 'Champagner'], ['#ffb4d2', 'Rosé'], ['#b4ffd2', 'Mint'], ['#d2b4ff', 'Flieder'], ['#e6e6e6', 'Neutral']];
  const STYLES = { clear: ['Klar', { blur: 4, glass: 0.6, solid: 0 }], frosted: ['Matt', { blur: 18, glass: 1, solid: 0 }],
    faded: ['Verblasst', { blur: 24, glass: 1, solid: 0 }], solid: ['Massiv', { blur: 18, glass: 1, solid: 1 }] };
  const DEFAULT = { accent: '#4fd8ff', tint: '#96c8ff', style: 'frosted', strength: 100 };
  let t = { ...DEFAULT };
  try { t = { ...DEFAULT, ...JSON.parse(localStorage.getItem(KEY) || '{}') }; } catch { /* private window */ }

  const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(' ');
  function apply() {
    const r = document.documentElement.style, st = STYLES[t.style] || STYLES.frosted;
    r.setProperty('--accent', t.accent);
    r.setProperty('--tint', rgb(t.tint));
    r.setProperty('--blur', `${st[1].blur}px`);
    r.setProperty('--glass', String(st[1].glass * t.strength / 100));
    r.setProperty('--solid', String(st[1].solid));
    document.documentElement.dataset.glass = t.style;
  }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(t)); } catch { /* private window */ } };

  const panel = document.getElementById('themePanel'), btn = document.getElementById('themeBtn');
  const swatches = (list, cur, key) => `<div class="sw">${list.map(([c, n]) =>
    `<button type="button" data-k="${key}" data-v="${c}" title="${n}" style="background:${c}" class="${c === cur ? 'on' : ''}"></button>`).join('')}
    <input type="color" data-k="${key}" value="${cur}" title="eigene Farbe" /></div>`;
  function paint() {
    panel.innerHTML = `
      <div class="th-head"><b>Einstellungen</b><button type="button" class="th-close" data-k="close" aria-label="Schließen">✕</button></div>
      <div><span class="th-label">Akzentfarbe</span>${swatches(ACCENTS, t.accent, 'accent')}</div>
      <div><span class="th-label">Glasfarbe der Karten</span>${swatches(TINTS, t.tint, 'tint')}</div>
      <div><span class="th-label">Glas</span><div class="seg">${Object.entries(STYLES).map(([k, [n]]) =>
        `<button type="button" data-k="style" data-v="${k}" class="${k === t.style ? 'on' : ''}">${n}</button>`).join('')}</div></div>
      <div><span class="th-label">Farbstärke ${t.strength} %</span><input type="range" min="20" max="200" step="10" data-k="strength" value="${t.strength}" /></div>
      <button type="button" class="th-reset" data-k="reset">Zurücksetzen</button>`;
  }
  function set(k, v) {
    if (k === 'reset') t = { ...DEFAULT };
    else t[k] = k === 'strength' ? Number(v) : v;
    apply(); save();
  }
  panel.addEventListener('click', (e) => { const b = e.target.closest('button[data-k]'); if (!b) return;
    if (b.dataset.k === 'close') { panel.hidden = true; return; }
    set(b.dataset.k, b.dataset.v); paint(); });
  panel.addEventListener('input', (e) => { const i = e.target.closest('input[data-k]'); if (!i) return; set(i.dataset.k, i.value);
    if (i.type === 'range') panel.querySelector('[data-k=strength]').previousElementSibling.textContent = `Farbstärke ${t.strength} %`; });
  panel.addEventListener('change', paint);
  btn.addEventListener('click', (e) => { e.stopPropagation(); paint(); panel.hidden = !panel.hidden; });
  apply();
})();
