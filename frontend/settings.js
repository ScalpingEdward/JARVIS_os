// Settings (the gear in the bottom bar): a menu of sections; "Design" holds everything
// about the look -- room, accent, glass, clock. Kept in this browser (localStorage).
(() => {
  const KEY = 'auron_theme';
  const ACCENTS = [['#4fd8ff', 'Cyan'], ['#f5b84a', 'Gold'], ['#ff7eb6', 'Rosa'], ['#3ddc97', 'Grün'], ['#b88cff', 'Lila'], ['#f2f4f8', 'Weiß']];
  const TINTS = [['#96c8ff', 'Eisblau'], ['#ffd28c', 'Champagner'], ['#ffb4d2', 'Rosé'], ['#b4ffd2', 'Mint'], ['#d2b4ff', 'Flieder'], ['#e6e6e6', 'Neutral']];
  const STYLES = { clear: ['Klar', { blur: 4, glass: 0.6, solid: 0 }], frosted: ['Matt', { blur: 18, glass: 1, solid: 0 }],
    faded: ['Verblasst', { blur: 24, glass: 1, solid: 0 }], solid: ['Massiv', { blur: 18, glass: 1, solid: 1 }] };
  const CLOCKS = { clean: 'Klar', thin: 'Dünn', mono: 'Digital', elegant: 'Elegant', neon: 'Neon', bold: 'Fett' };
  const DEFAULT = { accent: '#4fd8ff', tint: '#96c8ff', style: 'frosted', strength: 100, clock: 'clean', clockSize: 72 };
  const SECTIONS = [
    ['design', '🎨', 'Design', 'Raum, Farben, Glas, Uhr'],
    ['voice', '🔊', 'Stimme', 'AURONs Stimme wählen und anhören'],
    ['info', 'ℹ', 'Info', 'Was läuft, Versionen, Hinweise'],
  ];
  let t = { ...DEFAULT };
  try { t = { ...DEFAULT, ...JSON.parse(localStorage.getItem(KEY) || '{}') }; } catch { /* private window */ }
  let page = 'home';

  const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(' ');
  function apply() {
    const r = document.documentElement.style, st = STYLES[t.style] || STYLES.frosted;
    r.setProperty('--accent', t.accent);
    r.setProperty('--tint', rgb(t.tint));
    r.setProperty('--blur', `${st[1].blur}px`);
    r.setProperty('--glass', String(st[1].glass * t.strength / 100));
    r.setProperty('--solid', String(st[1].solid));
    r.setProperty('--clock-size', `${t.clockSize}px`);
    document.documentElement.dataset.glass = t.style;
    document.documentElement.dataset.clock = t.clock;
  }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(t)); } catch { /* private window */ } };

  const panel = document.getElementById('themePanel'), btn = document.getElementById('themeBtn');
  const swatches = (list, cur, key) => `<div class="sw">${list.map(([c, n]) =>
    `<button type="button" data-k="${key}" data-v="${c}" title="${n}" style="background:${c}" class="${c === cur ? 'on' : ''}"></button>`).join('')}
    <label class="own" title="eigene Farbe"><input type="color" data-k="${key}" value="${cur}" />+</label></div>`;
  const section = (title, body) => `<section class="th-sec"><h4>${title}</h4>${body}</section>`;
  const now = () => new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });

  function paint() {
    const head = (title, back) => `<div class="th-head">${back ? '<button type="button" class="th-back" data-k="back">‹</button>' : ''}
      <b>${title}</b><button type="button" class="th-close" data-k="close" aria-label="Schließen">✕</button></div>`;
    if (page === 'home') {
      panel.innerHTML = head('Einstellungen') + `<div class="th-menu">${SECTIONS.map(([k, ic, n, d]) =>
        `<button type="button" data-k="page" data-v="${k}"><i>${ic}</i><span><b>${n}</b><small>${d}</small></span><em>›</em></button>`).join('')}</div>`;
      return;
    }
    if (page === 'design') {
      const rooms = window.AURON_room ? window.AURON_room.list() : [];
      const cur = window.AURON_room ? window.AURON_room.get() : '';
      panel.innerHTML = head('Design', true)
        + section('Hintergrund', `<div class="th-rooms">${rooms.map((r) =>
          `<button type="button" data-k="room" data-v="${r.key}" class="${r.key === cur ? 'on' : ''}"><i style="background-image:url('${r.src}')"></i><span>${r.name}</span></button>`).join('')}</div>`)
        + section('Farben', `<span class="th-label">Akzent</span>${swatches(ACCENTS, t.accent, 'accent')}
            <span class="th-label">Glas der Karten</span>${swatches(TINTS, t.tint, 'tint')}`)
        + section('Glas', `<div class="seg">${Object.entries(STYLES).map(([k, [n]]) =>
            `<button type="button" data-k="style" data-v="${k}" class="${k === t.style ? 'on' : ''}">${n}</button>`).join('')}</div>
            <span class="th-label">Farbstärke <b data-out="strength">${t.strength} %</b></span>
            <input type="range" min="20" max="200" step="10" data-k="strength" value="${t.strength}" />`)
        + section('Uhr', `<div class="th-clocks">${Object.entries(CLOCKS).map(([k, n]) =>
            `<button type="button" data-k="clock" data-v="${k}" class="${k === t.clock ? 'on' : ''}"><b class="ck-${k}">${now()}</b><span>${n}</span></button>`).join('')}</div>
            <span class="th-label">Größe <b data-out="clockSize">${t.clockSize} px</b></span>
            <input type="range" min="40" max="120" step="4" data-k="clockSize" value="${t.clockSize}" />`)
        + '<button type="button" class="th-reset" data-k="reset">Design zurücksetzen</button>';
      return;
    }
    if (page === 'info') {
      panel.innerHTML = head('Info', true) + section('AURON', `<p class="th-text">Dashboard, Kopierer, Instagram, Post und Smart Money laufen
        auf diesem Laptop. Design-Einstellungen gelten für diesen Browser. Den Status der Dienste zeigt die Leiste unten.</p>`);
    }
  }

  function set(k, v) {
    if (k === 'reset') t = { ...DEFAULT };
    else t[k] = k === 'strength' || k === 'clockSize' ? Number(v) : v;
    apply(); save();
  }
  panel.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-k]');
    if (!b) return;
    const { k, v } = b.dataset;
    if (k === 'close') { panel.hidden = true; page = 'home'; return; }
    if (k === 'back') { page = 'home'; paint(); return; }
    if (k === 'page') {
      if (v === 'voice') { panel.hidden = true; page = 'home'; document.getElementById('chatVoices')?.click(); return; }
      page = v; paint(); return;
    }
    if (k === 'room') { window.AURON_room?.set(v); paint(); return; }
    set(k, v); paint();
  });
  panel.addEventListener('input', (e) => {
    const i = e.target.closest('input[data-k]');
    if (!i) return;
    set(i.dataset.k, i.value);
    const out = panel.querySelector(`[data-out="${i.dataset.k}"]`);
    if (out) out.textContent = i.dataset.k === 'strength' ? `${t.strength} %` : `${t.clockSize} px`;
  });
  panel.addEventListener('change', (e) => { if (e.target.type === 'color') paint(); });
  btn.addEventListener('click', (e) => { e.stopPropagation(); page = 'home'; paint(); panel.hidden = !panel.hidden; });
  apply();
})();
