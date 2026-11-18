# syntax=docker/dockerfile:1
# Edge image: Caddy + built React static files. Build from repo root.
FROM node:24-bookworm-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Same-origin: empty base so the browser calls /api and /auth on the public host.
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM caddy:2.9-alpine
COPY infra/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-build /app/dist /srv
EXPOSE 80 443
