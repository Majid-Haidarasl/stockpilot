# ADR-004 — Login and opaque session

- **Status:** Accepted-in-principle, to be confirmed at implementation
- **Date:** 2026-11-11

## Question

Why does the browser hold an opaque session id, and why are OIDC tokens stored server-side?

## Plan direction (not yet coded)

Keycloak authenticates via Authorization Code + PKCE. FastAPI creates a local session. The browser receives only a random session id cookie (`HttpOnly`, `Secure`, `SameSite=Lax`). Tokens are not placed in `localStorage` or JS-readable cookies; if kept for refresh/logout, they are stored server-side, encrypted, with a key outside the database. CSRF token + Origin checks on mutating requests.

## Consequences (expected)

- Product backend does not store passwords.
- Organizational roles are re-checked from app membership on every request.
- Exact back-channel logout policy remains an **OPEN DECISION**.
