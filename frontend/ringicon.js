// The window's icon (tab, title bar): the AURON ring, breathing very slightly -- its glow rises and falls
// over six seconds (Brano, 2026-10-23). The logo is the ring alone, no light on it. The icons on the desktop
// and the phone's home screen cannot move; they show the same ring still (tools/make_ring_icon.py).
(() => {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d');
  let link = document.querySelector('link[rel="icon"]');
  if (!link) { link = document.createElement('link'); link.rel = 'icon'; document.head.append(link); }
  document.querySelectorAll('link[rel="icon"]').forEach((l) => { if (l !== link) l.remove(); });
  function draw(t) {
    const glow = 6 + 5 * (0.5 + 0.5 * Math.sin((t / 6000) * Math.PI * 2));
    g.clearRect(0, 0, 64, 64);
    g.fillStyle = '#03050a'; g.beginPath(); g.arc(32, 32, 32, 0, 7); g.fill();
    g.strokeStyle = '#4fd8ff'; g.lineWidth = 5; g.shadowColor = '#4fd8ff'; g.shadowBlur = glow;
    g.beginPath(); g.arc(32, 32, 19, 0, 7); g.stroke();
    g.shadowBlur = 0;
    link.type = 'image/png'; link.href = c.toDataURL('image/png');
  }
  draw(0);
  // reduced motion: the ring stands still (on the LG TV nobody sees a tab icon, and it cost the chip time)
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  setInterval(() => { if (!document.hidden) draw(performance.now()); }, 250);
})();
