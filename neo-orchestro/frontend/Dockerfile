# syntax=docker/dockerfile:1
# Neo-Orchestro web image: static build served by an unprivileged nginx, which also proxies
# /api and /health to the API so the browser sees a single origin (cookies stay same-origin).
# Designed & Developed by Ronald TSR.

# ---------- build ------------------------------------------------------------------------------
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
# --ignore-scripts: no dependency may run code at install time (supply-chain hardening).
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build

# ---------- runtime ----------------------------------------------------------------------------
# Pin by digest in release builds. This image runs as the unprivileged "nginx" user on 8080.
FROM nginxinc/nginx-unprivileged:stable-alpine AS runtime
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["wget", "-qO-", "http://127.0.0.1:8080/healthz"]
