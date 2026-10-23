FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html styles.css app.js chat.js room.js settings.js cardview.js layout.js announce.js desk.js look.js code.js persona.js chart.js live.js ui.js model.js approve.js ringicon.js push.js sw.js ticket.js charttools.js lang.js demo.js globe.js lounge.webp auron.ico auron-planet.ico icon-192.png icon-512.png app-icon-192.png app-icon-512.png app-icon-maskable-512.png apple-touch-icon.png manifest.webmanifest /usr/share/nginx/html/
COPY rooms /usr/share/nginx/html/rooms
COPY site /usr/share/nginx/html/site
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD wget -qO- http://127.0.0.1/healthz || exit 1
