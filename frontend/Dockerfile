FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html styles.css app.js chat.js room.js settings.js cardview.js demo.js globe.js lounge.webp /usr/share/nginx/html/
COPY rooms /usr/share/nginx/html/rooms
COPY site /usr/share/nginx/html/site
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD wget -qO- http://127.0.0.1/healthz || exit 1
