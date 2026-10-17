// A gear on every card (shows on hover): how the card lays out its list -- rows or small tiles.
// Kept per card in this browser.
(() => {
  const KEY = 'auron_cardview';
  const CARDS = { tileTrading: '#tGroups', tileWatch: '#wTop', tileInstagram: '#iList', tileMail: '#mList', tileSmart: '#sInsider' };
  let views = {};
  try { views = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { views = {}; }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(views)); } catch { /* private window */ } };
  const apply = (id) => document.querySelector(CARDS[id])?.classList.toggle('as-tiles', views[id] === 'tiles');

  for (const id of Object.keys(CARDS)) {
    const card = document.getElementById(id);
    if (!card) continue;
    const gear = document.createElement('span');
    gear.className = 'card-gear'; gear.setAttribute('role', 'button'); gear.title = 'Ansicht der Karte'; gear.textContent = '⚙';
    const menu = document.createElement('span');
    menu.className = 'card-menu'; menu.hidden = true;
    const paint = () => { menu.innerHTML = [['list', '☰ Liste'], ['tiles', '▦ Kacheln']].map(([v, t]) =>
      `<span role="button" data-v="${v}" class="${(views[id] || 'list') === v ? 'on' : ''}">${t}</span>`).join(''); };
    card.append(gear, menu);
    // the card itself is a button that opens its view -- clicks on the gear and menu stay here
    gear.addEventListener('click', (e) => { e.stopPropagation(); e.preventDefault(); paint(); menu.hidden = !menu.hidden; card.classList.toggle('menu-open', !menu.hidden); });
    menu.addEventListener('click', (e) => {
      e.stopPropagation(); e.preventDefault();
      const b = e.target.closest('[data-v]'); if (!b) return;
      views[id] = b.dataset.v; save(); apply(id); paint();
    });
    apply(id);
  }
  document.addEventListener('click', () => document.querySelectorAll('.card-menu').forEach((m) => {
    if (!m.hidden) { m.hidden = true; m.parentElement.classList.remove('menu-open'); } }));
})();
