// A gear on every card (shows on hover): how the card lays out its list -- rows or small tiles --
// and how its text looks: size (A− / A+), the numbers' size on their own, and one of six typefaces,
// for this card or all of them. Kept per card in this browser.
// The card itself never grows with its text (Brano, 2026-10-19): it keeps the height it has at 100 %,
// larger text pushes the last list rows out, and the size stops at the step where something no
// longer fits -- a figure or a number column running over its neighbour.
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
  const NUMS = [0.9, 1, 1.12, 1.25, 1.4, 1.55];   // on top of the text size, numbers only
  const NUM_SEL = '.tile-figure b, .kpis b, .tile-list .row > span:last-child, .tile-list .row.grp > span:nth-child(3), .mono';
  const DEFAULT = { size: 1.12, font: 'std', num: 1 };   // a little larger than before (Brano, 2026-10-19)
  const load = (k) => { try { return JSON.parse(localStorage.getItem(k) || '{}'); } catch { return {}; } };
  let views = load(KEY), styles = load(STYLE_KEY);
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(views)); localStorage.setItem(STYLE_KEY, JSON.stringify(styles)); } catch { /* private window */ } };
  const styleOf = (id) => ({ ...DEFAULT, ...(styles[id] || {}) });

  const kids = (card) => [...card.children].filter((el) => !el.matches('.corner, .card-gear'));
  // something runs over its box: a number column wider than its cell, the card wider than itself.
  // Names cut off with "…" are meant to be cut, they don't count -- a number cut off does.
  const spills = (card) => card.scrollWidth > card.clientWidth + 1 || [...card.querySelectorAll('*')].some((el) =>
    el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0
    && (getComputedStyle(el).textOverflow !== 'ellipsis' || el.matches(NUM_SEL)));

  function fit(id) {
    const card = document.getElementById(id);
    if (!card) return;
    const st = styleOf(id), parts = kids(card), lists = [...card.querySelectorAll('.tile-list > *')];
    const zoom = (z, n) => { parts.forEach((el) => { el.style.zoom = z === 1 ? '' : String(z); });
      card.querySelectorAll(NUM_SEL).forEach((el) => { el.style.zoom = n === 1 ? '' : String(n); }); };
    lists.forEach((el) => { el.style.display = ''; });
    card.style.height = ''; zoom(1, 1);
    const h = card.offsetHeight;
    if (!h) return;                       // parked or hidden: measured when it shows
    card.style.height = `${h}px`;
    const pad = parseFloat(getComputedStyle(card).paddingBottom) || 0;
    const bottom = () => card.getBoundingClientRect().top + card.clientTop + card.clientHeight - pad;
    // from the chosen size downwards, the first step at which the fixed parts fit
    let used = 1;
    for (let i = SIZES.indexOf(st.size); i >= 0; i--) {
      const z = SIZES[i];
      zoom(z, st.num);
      const lim = bottom() + 1;
      const fixed = parts.filter((el) => !el.classList.contains('tile-list'));
      const overTop = fixed.some((el) => el.getBoundingClientRect().bottom > lim);
      used = z;
      if (z <= 1 || (!overTop && !spills(card))) break;
    }
    // still running over at 100 % text: then the numbers give way too
    let num = st.num;
    for (let j = NUMS.indexOf(st.num); j > 0 && spills(card); j--) { num = NUMS[j - 1]; zoom(used, num); }
    // rows that no longer fit leave whole, never half
    const lim = bottom() + 1;
    lists.forEach((el) => { if (el.getBoundingClientRect().bottom > lim) el.style.display = 'none'; });
    card.dataset.fit = String(used); card.dataset.fitNum = String(num);
  }

  function apply(id) {
    document.querySelector(CARDS[id])?.classList.toggle('as-tiles', views[id] === 'tiles');
    const card = document.getElementById(id);
    if (!card) return;
    const st = styleOf(id);
    card.style.zoom = '';
    card.style.fontFamily = st.font === 'std' ? '' : FONTS[st.font][1];
    card.dataset.font = st.font;
    fit(id);
  }
  // the lists are re-rendered with every refresh: fit again once the new rows are in
  const pending = new Set();
  const refit = (id) => { if (pending.has(id)) return; pending.add(id);
    setTimeout(() => { pending.delete(id); fit(id); }, 30); };   // not rAF: it sleeps in a hidden window

  for (const id of Object.keys(CARDS)) {
    const card = document.getElementById(id);
    if (!card) continue;
    const gear = document.createElement('span');
    gear.className = 'card-gear'; gear.setAttribute('role', 'button'); gear.title = 'Ansicht der Karte'; gear.textContent = '⚙';
    const menu = document.createElement('span');
    menu.className = 'card-menu'; menu.hidden = true;
    const paint = () => {
      const st = styleOf(id), i = SIZES.indexOf(st.size), j = NUMS.indexOf(st.num), f = Number(card.dataset.fit || st.size), fn = Number(card.dataset.fitNum || st.num);
      menu.innerHTML = `<b class="cm-h">Ansicht</b>`
        + [['list', '☰ Liste'], ['tiles', '▦ Kacheln']].map(([v, t]) =>
          `<span role="button" data-v="${v}" class="${(views[id] || 'list') === v ? 'on' : ''}">${t}</span>`).join('')
        + `<b class="cm-h">Schriftgröße</b><span class="cm-size"><i role="button" data-size="-1" class="${i <= 0 ? 'off' : ''}">A−</i>`
        + `<em>${Math.round(st.size * 100)} %</em><i role="button" data-size="1" class="${i >= SIZES.length - 1 ? 'off' : ''}">A+</i></span>`
        + (f < st.size ? `<small class="cm-note">passt bis ${Math.round(f * 100)} %</small>` : '')
        + `<b class="cm-h">Zahlen</b><span class="cm-size"><i role="button" data-num="-1" class="${j <= 0 ? 'off' : ''}">A−</i>`
        + `<em>${Math.round(st.num * 100)} %</em><i role="button" data-num="1" class="${j >= NUMS.length - 1 ? 'off' : ''}">A+</i></span>`
        + (fn < st.num ? `<small class="cm-note">passt bis ${Math.round(fn * 100)} %</small>` : '')
        + `<b class="cm-h">Schriftart</b>`
        + Object.entries(FONTS).map(([k, [n, fam]]) =>
          `<span role="button" data-font="${k}" class="${st.font === k ? 'on' : ''}" style='font-family:${fam}'>${n}</span>`).join('')
        + `<span role="button" data-all="1" class="cm-all">Für alle Karten übernehmen</span>`;
    };
    card.append(gear);
    // The menu lives on the page, not in the card: inside, it covered the card's own content and a
    // card that clips (Post) cut it off. It opens beside the card, toward the middle of the screen --
    // to the right of a card on the left, to the left of a card on the right.
    menu.dataset.card = id;
    document.body.append(menu);
    const place = () => {
      const r = card.getBoundingClientRect(), w = menu.offsetWidth, h = menu.offsetHeight;
      const onLeft = r.left + r.width / 2 < innerWidth / 2;
      let x = onLeft ? r.right + 10 : r.left - w - 10;
      if (x < 8 || x + w > innerWidth - 8) x = Math.min(Math.max(8, r.right - w - 10), innerWidth - w - 8);   // narrow screen: over the card
      menu.style.left = `${x}px`;
      menu.style.top = `${Math.min(Math.max(8, r.top + 8), innerHeight - h - 8)}px`;
    };
    // the card itself is a button that opens its view -- clicks on the gear and menu stay here
    gear.addEventListener('click', (e) => {
      e.stopPropagation(); e.preventDefault();
      const open = menu.hidden;
      document.querySelectorAll('.card-menu').forEach((m) => { m.hidden = true; document.getElementById(m.dataset.card)?.classList.remove('menu-open'); });
      if (open) { paint(); menu.hidden = false; place(); card.classList.add('menu-open'); }
    });
    menu.addEventListener('click', (e) => {
      e.stopPropagation(); e.preventDefault();
      const b = e.target.closest('[data-v], [data-size], [data-num], [data-font], [data-all]');
      if (!b) return;
      const st = styleOf(id);
      if (b.dataset.v) views[id] = b.dataset.v;
      if (b.dataset.size) {
        const i = Math.min(SIZES.length - 1, Math.max(0, SIZES.indexOf(st.size) + Number(b.dataset.size)));
        styles[id] = { ...st, size: SIZES[i] };
      }
      if (b.dataset.num) {
        const j = Math.min(NUMS.length - 1, Math.max(0, NUMS.indexOf(st.num) + Number(b.dataset.num)));
        styles[id] = { ...st, num: NUMS[j] };
      }
      if (b.dataset.font) styles[id] = { ...st, font: b.dataset.font };
      if (b.dataset.all) Object.keys(CARDS).forEach((other) => { styles[other] = { ...styleOf(id) }; apply(other); });
      save(); apply(id); paint(); place();
    });
    new MutationObserver(() => refit(id)).observe(card, { childList: true, subtree: true, characterData: true });
    apply(id);
  }
  addEventListener('resize', () => Object.keys(CARDS).forEach(refit));
  document.fonts?.ready.then(() => Object.keys(CARDS).forEach(refit));
  const closeAll = () => document.querySelectorAll('.card-menu').forEach((m) => {
    if (!m.hidden) { m.hidden = true; document.getElementById(m.dataset.card)?.classList.remove('menu-open'); } });
  document.addEventListener('click', closeAll);
  addEventListener('resize', closeAll);
})();
