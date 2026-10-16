// The rooms behind AURON. Coordinates are fractions of the picture (0..1, from top left).
// ped: centre of the pedestal's top surface and that surface's width -- the planet stands there.
// zones: [effect, x0, y0, x1, y1] -- room.js animates only inside them, so a column
// next to a window never ripples:
//   sway    plants: the top moves, the pot stays        water   ripples and glitter
//   clouds  slow drift of the sky                       stars   small bright points twinkle
//   city    warm city lights twinkle                    sun     the sun's glow breathes
//   glow    the light strips breathe                    flicker warm light, a candle's unrest
//   sheen   a slow band of light across the polished floor
window.AURON_ROOMS = {
  lounge: { name: 'Lounge bei Nacht', src: 'lounge.webp', w: 1672, h: 941, ped: [0.501, 0.605, 0.335], zones: [
    ['water', 0.44, 0.457, 0.71, 0.537], ['city', 0.06, 0.38, 0.96, 0.505], ['clouds', 0.28, 0.20, 0.64, 0.33], ['clouds', 0.77, 0.20, 0.94, 0.32],
    ['stars', 0.06, 0.10, 0.96, 0.30],
    ['sway', 0.0, 0.35, 0.07, 0.49], ['sway', 0.93, 0.35, 0.99, 0.49], ['glow', 0, 0, 1, 1], ['sheen', 0, 0.56, 1, 1]] },
  noir: { name: 'Noir', src: 'rooms/noir.webp', w: 3344, h: 1882, ped: [0.500, 0.608, 0.43], zones: [
    ['sway', 0.00, 0.33, 0.12, 0.535], ['sway', 0.19, 0.39, 0.29, 0.515], ['sway', 0.71, 0.39, 0.81, 0.515], ['sway', 0.88, 0.33, 1.00, 0.535],
    ['glow', 0, 0, 1, 0.6], ['sheen', 0, 0.58, 1, 1]] },
  gold: { name: 'Gold', src: 'rooms/gold.webp', w: 3344, h: 1882, ped: [0.500, 0.614, 0.395], zones: [
    ['sway', 0.00, 0.36, 0.10, 0.545], ['sway', 0.20, 0.41, 0.30, 0.525], ['sway', 0.70, 0.41, 0.80, 0.525], ['sway', 0.89, 0.36, 1.00, 0.545],
    ['flicker', 0, 0, 1, 0.62], ['sheen', 0, 0.6, 1, 1]] },
  orbit: { name: 'Orbit', src: 'rooms/orbit.webp', w: 4000, h: 2250, ped: [0.500, 0.752, 0.463], zones: [
    ['stars', 0.17, 0.12, 0.83, 0.66], ['glow', 0, 0, 1, 1]] },
  alps: { name: 'Alpen bei Sonnenuntergang', src: 'rooms/alps.webp', w: 3344, h: 1882, ped: [0.500, 0.626, 0.40], zones: [
    ['clouds', 0.27, 0.19, 0.73, 0.36], ['clouds', 0.03, 0.13, 0.21, 0.32], ['clouds', 0.80, 0.15, 0.97, 0.32], ['clouds', 0.37, 0.0, 0.63, 0.085],
    ['water', 0.40, 0.47, 0.77, 0.53], ['sun', 0.64, 0.36, 0.74, 0.47],
    ['sway', 0.00, 0.29, 0.13, 0.50], ['sway', 0.19, 0.39, 0.28, 0.48], ['sway', 0.72, 0.39, 0.81, 0.48], ['sway', 0.94, 0.33, 1.00, 0.50],
    ['sheen', 0, 0.6, 1, 1]] },
  earth: { name: 'Über der Erde', src: 'rooms/earth.webp', w: 3344, h: 1882, ped: [0.500, 0.606, 0.43], zones: [
    ['stars', 0.28, 0.17, 0.72, 0.345], ['stars', 0.03, 0.12, 0.20, 0.30], ['stars', 0.79, 0.12, 0.97, 0.30],
    ['city', 0.28, 0.36, 0.72, 0.53], ['glow', 0, 0, 1, 1],
    ['sway', 0.00, 0.29, 0.10, 0.50], ['sway', 0.19, 0.40, 0.27, 0.49], ['sway', 0.70, 0.40, 0.78, 0.49], ['sway', 0.89, 0.29, 1.00, 0.50]] },
};
