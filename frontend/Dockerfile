# =============================================================================
# Prof IA v6.0 — Dockerfile Frontend React
# =============================================================================
# FIX BUG#2 : Ce fichier était absent — docker compose build échouait

FROM node:20-alpine AS builder

WORKDIR /app

# Dépendances
COPY package*.json .npmrc ./
RUN npm ci --legacy-peer-deps

# Build de production
# react-scripts (webpack 5) échoue sur Node ≥17 / OpenSSL 3 avec
# "digital envelope routines::unsupported" → on force le legacy provider.
COPY . .
ENV NODE_OPTIONS=--openssl-legacy-provider
RUN npm run build

# ── Image de production (nginx statique) ──────────────────────────────────────
FROM nginx:alpine AS production

# Copier le build React
COPY --from=builder /app/build /usr/share/nginx/html

# Config nginx pour React Router (SPA)
RUN echo 'server { \
    listen 3000; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { try_files $uri $uri/ /index.html; } \
    location /health { return 200 "ok"; } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s \
    CMD wget -q --spider http://localhost:3000/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
