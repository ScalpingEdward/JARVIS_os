// A gear on every card (shows on hover): how the card lays out its list -- rows or small tiles --
// and how its text looks: size (A− / A+) and one of six typefaces, for this card or all of them.
// Kept per card in this browser.
(() => {
  const KEY = 'auron_cardview', STYLE_KEY = 'auron_cardstyle';
  const CARDS = { tileTrading: '#tGroups', tileWatch: '#wTop', tileInstagram: '#iList', tileMail: '#mList', tileSmart: '#sInsider' };
  // the typefaces (index.html loads them from Google Fonts); "std" is the dashboard's own
  const FONTS = {
    std: ['Standard', 'Inter, "Segoe UI", system-ui, sans-serif'],
    exo: ['Exo 2', '"Exo 2", "Segoe UI", sans-serif'],
    rajdhani: ['Rajdhani', 'Rajdhani, "Segoe UI", sans-serif'],
    sora: ['Sora', 'Sora, "Segoe UI", sans-serif'],
    oxanium: ['Oxanium', 'Oxanium, "Segoe UI", sans-serif'],
    manrope: ['Manrope', 'Manrope, "Segoe UI", sans-serif'],
  };
  const SIZES = [0.9, 1, 1.12, 1.25, 1.4, 1.55];
  const DEFAULT = { size: 1.12, font: 'std' };   // a little larger than before (Brano, 2026-10-19)
  const load = (k) => { try { return JSON.parse(localStorage.getItem(k) || '{}'); } catch { return {}; } };
  let views = load(KEY), styles = load(STYLE_KEY);
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(views)); localStorage.setItem(STYLE_KEY, JSON.stringify(styles)); } catch { /* private window */ } };
  const styleOf = (id) => ({ ...DEFAULT, ...(styles[id] || {}) });

  function apply(id) {
    document.querySelector(CARDS[id])?.classList.toggle('as-tiles', views[id] === 'tiles');
    const card = document.getElementById(id);
    if (!card) return;
    const st = styleOf(id);
    card.style.zoom = String(st.size);
    card.style.fontFamily = st.font === 'std' ? '' : FONTS[st.font][1];
    card.dataset.font = st.font;
  }

  for (const id of Object.keys(CARDS)) {
    const card = document.getElementById(id);
    if (!card) continue;
    const gear = document.createElement('span');
    gear.className = 'card-gear'; gear.setAttribute('role', 'button'); gear.title = 'Ansicht der Karte'; gear.textContent = '⚙';
    const menu = document.createElement('span');
    menu.className = 'card-menu'; menu.hidden = true;
    const paint = () => {
      const st = styleOf(id), i = SIZES.indexOf(st.size);
      menu.innerHTML = `<b class="cm-h">Ansicht</b>`
        + [['list', '☰ Liste'], ['tiles', '▦ Kacheln']].map(([v, t]) =>
          `<span role="button" data-v="${v}" class="${(views[id] || 'list') === v ? 'on' : ''}">${t}</span>`).join('')
        + `<b class="cm-h">Schriftgröße</b><span class="cm-size"><i role="button" data-size="-1" class="${i <= 0 ? 'off' : ''}">A−</i>`
        + `<em>${Math.round(st.size * 100)} %</em><i role="button" data-size="1" class="${i >= SIZES.length - 1 ? 'off' : ''}">A+</i></span>`
        + `<b class="cm-h">Schriftart</b>`
        + Object.entries(FONTS).map(([k, [n, fam]]) =>
          `<span role="button" data-font="${k}" class="${st.font === k ? 'on' : ''}" style='font-family:${fam}'>${n}</span>`).join('')
        + `<span role="button" data-all="1" class="cm-all">Für alle Karten übernehmen</span>`;
    };
    card.append(gear, menu);
    // the card itself is a button that opens its view -- clicks on the gear and menu stay here
    gear.addEventListener('click', (e) => { e.stopPropagation(); e.preventDefault(); paint(); menu.hidden = !menu.hidden; card.classList.toggle('menu-open', !menu.hidden); });
    menu.addEventListener('click', (e) => {
      e.stopPropagation(); e.preventDefault();
      const b = e.target.closest('[data-v], [data-size], [data-font], [data-all]');
      if (!b) return;
      const st = styleOf(id);
      if (b.dataset.v) views[id] = b.dataset.v;
      if (b.dataset.size) {
        const i = Math.min(SIZES.length - 1, Math.max(0, SIZES.indexOf(st.size) + Number(b.dataset.size)));
        styles[id] = { ...st, size: SIZES[i] };
      }
      if (b.dataset.font) styles[id] = { ...st, font: b.dataset.font };
      if (b.dataset.all) Object.keys(CARDS).forEach((other) => { styles[other] = { ...styleOf(id) }; apply(other); });
      save(); apply(id); paint();
    });
    apply(id);
  }
  document.addEventListener('click', () => document.querySelectorAll('.card-menu').forEach((m) => {
    if (!m.hidden) { m.hidden = true; m.parentElement.classList.remove('menu-open'); } }));
})();
