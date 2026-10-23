// The window's icon (tab, title bar): the AURON ring with its small light slowly circling -- one turn in eight
// seconds, barely there (Brano, 2026-10-23). The icons on the desktop and the phone's home screen cannot
// move; they show the same ring with the light standing (tools/make_ring_icon.py).
(() => {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d');
  let link = document.querySelector('link[rel="icon"]');
  if (!link) { link = document.createElement('link'); link.rel = 'icon'; document.head.append(link); }
  document.querySelectorAll('link[rel="icon"]').forEach((l) => { if (l !== link) l.remove(); });
  function draw(t) {
    g.clearRect(0, 0, 64, 64);
    g.fillStyle = '#03050a'; g.beginPath(); g.arc(32, 32, 32, 0, 7); g.fill();
    g.strokeStyle = '#4fd8ff'; g.lineWidth = 5; g.shadowColor = '#4fd8ff'; g.shadowBlur = 8;
    g.beginPath(); g.arc(32, 32, 19, 0, 7); g.stroke();
    const a = -0.9 + (t / 8000) * Math.PI * 2;
    g.shadowColor = '#ffffff'; g.shadowBlur = 6; g.fillStyle = '#ffffff';
    g.beginPath(); g.arc(32 + 19 * Math.cos(a), 32 + 19 * Math.sin(a), 2.6, 0, 7); g.fill();
    g.shadowBlur = 0;
    link.type = 'image/png'; link.href = c.toDataURL('image/png');
  }
  draw(0);
  setInterval(() => { if (!document.hidden) draw(performance.now()); }, 200);
})();
