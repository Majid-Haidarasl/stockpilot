# Database roles (Phase 1)

| Role | Database | Purpose |
|---|---|---|
| `stockpilot_migrator` | `stockpilot` | Schema owner. Used **only** by the one-shot `migrate` job / Alembic. |
| `stockpilot_app` | `stockpilot` | Runtime role for API (and later workers). Login, **no** superuser, **no** `BYPASSRLS`, not table owner. Prepared for RLS in T06. |
| `keycloak` | `keycloak` | Dedicated identity DB user. Product app never reads Keycloak tables. |

Default Compose wires:

- `STOCKPILOT_MIGRATION_DATABASE_URL` → migrator (migrate service only)
- `STOCKPILOT_DATABASE_URL` → `stockpilot_app` (API)

The API must not be configured to connect as the schema owner in the default Compose setup.
