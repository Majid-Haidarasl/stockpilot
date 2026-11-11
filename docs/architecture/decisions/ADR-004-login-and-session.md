# ADR-004 — Login and opaque session

- **Status:** Accepted
- **Date:** 2026-11-11

## Question

Why does the browser hold an opaque session id, and why are OIDC tokens stored server-side?

## Decision

- Keycloak authenticates with Authorization Code + PKCE.
- FastAPI handles `/auth/login` and `/auth/callback`.
- Browser receives only a random session id cookie (`HttpOnly`, `SameSite=Lax`, `Secure` configurable; off for local HTTP).
- Session lookup uses a SHA-256 hash of the cookie value.
- Refresh/ID tokens (if kept) are encrypted server-side with a key outside the database.
- CSRF token cookie (readable) + `X-CSRF-Token` header + Origin check on mutating routes.
- Idle timeout 30 minutes; absolute lifetime 8 hours.
- Public OIDC issuer is `http://localhost:8180/realms/stockpilot` by default (browser authorize URL + `iss` claim validation; host port is configurable because Windows Hyper-V often reserves 8080).
- API fetches discovery from internal `http://keycloak:8080/...`, then **rewrites** token/JWKS endpoints onto that Docker-internal host while keeping `iss` checks on the public issuer. Issuer checks are never disabled.

## Open

- Keycloak back-channel / immediate global logout policy remains an **OPEN DECISION**. Do not claim cross-service instant logout.

## Consequences

- Product backend does not store passwords.
- Organizational roles come from app membership (T06), not Keycloak realm roles.
