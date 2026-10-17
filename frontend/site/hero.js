// The hero works like the dashboard: each room is scaled and shifted so its pedestal stands
// right under AURON's planet (pedestal data from ../rooms/rooms.js), and the office moves
// through the rooms every 6 seconds.
(() => {
  const ROOMS = window.AURON_ROOMS || {};
  const tour = [['earth', 'Über der Erde'], ['alps', 'In den Alpen'], ['forest', 'Am Wasserfall'], ['gold', 'Im eigenen Turm'], ['lounge', 'Über der Stadt']]
    .filter(([k]) => ROOMS[k]);
  const a = document.getElementById('bgA'), b = document.getElementById('bgB'), where = document.getElementById('where');
  const core = document.getElementById('core');
  const src = (k) => `../${ROOMS[k].src}`;

  function place(layer, key) {
    const room = ROOMS[key], c = core.getBoundingClientRect(), hero = layer.parentElement.getBoundingClientRect();
    const px = c.left - hero.left + c.width / 2, py = c.top - hero.top + c.height * 0.88;
    const vw = hero.width, vh = hero.height, [x, y, top] = room.ped;
    let scale = Math.max(vw / room.w, vh / room.h, (c.width * 0.8) / (top * room.w));
    for (let i = 0; i < 40; i++) {
      const W = room.w * scale, H = room.h * scale, bx = px - x * W, by = py - y * H;
      if (bx <= 0 && by <= 0 && bx + W >= vw && by + H >= vh) {
        layer.style.backgroundImage = `url("${src(key)}")`;
        layer.style.backgroundSize = `${W}px ${H}px`;
        layer.style.backgroundPosition = `${bx}px ${by}px`;
        layer.dataset.room = key;
        return;
      }
      scale *= 1.05;
    }
  }
  let n = 0, front = a, back = b;
  place(front, tour[0][0]);
  addEventListener('resize', () => { place(front, front.dataset.room); if (back.dataset.room) place(back, back.dataset.room); });
  tour.forEach(([k]) => { const i = new Image(); i.src = src(k); });
  if (matchMedia('(prefers-reduced-motion: reduce)').matches || tour.length < 2) return;
  setInterval(() => {
    n = (n + 1) % tour.length;
    place(back, tour[n][0]);
    back.classList.remove('next'); front.classList.add('next');
    [front, back] = [back, front];
    where.style.opacity = 0;
    setTimeout(() => { where.textContent = tour[n][1]; where.style.opacity = 1; }, 600);
  }, 6000);
})();
