# =============================================================================
# Prof IA v5.8.3 — Dockerfile Frontend React
# =============================================================================
#
# CHANGELOG v5.8.3 :
#   [M1] user: root supprimé du docker-compose — nginx:alpine gère ses propres
#        permissions. Ce conteneur n'a pas besoin d'être root.
#   [M4] Version uniformisée à 5.8.3
#
# ARCHITECTURE multi-stage :
#   Stage 1 (builder) : node:20-alpine — compile le bundle React en production
#   Stage 2 (prod)    : nginx:alpine   — sert les fichiers statiques sur :3000
#
# REACT_APP_API_URL est injectée via environment dans docker-compose.yml
# et compilée dans le bundle au moment du build (variables REACT_APP_* = build time)
# =============================================================================

FROM node:20-alpine AS builder

LABEL version="5.8.3"

WORKDIR /app

COPY package*.json ./
RUN npm ci --silent

COPY . .
RUN npm run build

# ── Image de production ───────────────────────────────────────────────────────
FROM nginx:alpine AS production

LABEL version="5.8.3"

# Bundle React compilé
COPY --from=builder /app/build /usr/share/nginx/html

# Config nginx pour React Router (SPA — toutes les routes → index.html)
RUN echo 'server { \
    listen 3000; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { try_files $uri $uri/ /index.html; } \
    location /health { return 200 "ok"; add_header Content-Type text/plain; } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s \
    CMD wget -q --spider http://localhost:3000/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
