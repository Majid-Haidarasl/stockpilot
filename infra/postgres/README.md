# PostgreSQL init

Scripts in `init/` run once when the Postgres data volume is empty.

They create:

- databases `stockpilot` and `keycloak`
- roles `stockpilot_migrator` (schema owner), `stockpilot_app` (runtime), `keycloak`

Schema objects are created by Alembic (`migrate` service), not by these scripts.
