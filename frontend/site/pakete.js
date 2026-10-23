// The price packages as AURON boxes (Brano, 2026-10-23): a tap on a box lifts it and opens what is in
// that package right below -- the details card of the same package. Trader is open at first.
(() => {
  const boxes = [...document.querySelectorAll('.pk-box')], cards = [...document.querySelectorAll('.pk-details > .price')];
  function show(i, scroll) {
    boxes.forEach((b, k) => { b.classList.toggle('on', k === i); b.setAttribute('aria-expanded', String(k === i)); });
    cards.forEach((c, k) => c.classList.toggle('open', k === i));
    if (scroll) cards[i]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  boxes.forEach((b, i) => b.addEventListener('click', () => show(i, true)));
  show(2, false);
})();
