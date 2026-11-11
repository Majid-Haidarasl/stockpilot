"""Access identity: users, sessions, tenants, memberships.

Revision ID: 0002_access_identity
Revises: 0001_schemas
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_access_identity"
down_revision: str | None = "0001_schemas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE access.users (
            id UUID PRIMARY KEY,
            issuer TEXT NOT NULL,
            subject TEXT NOT NULL,
            email TEXT,
            display_name TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_access_users_issuer_subject UNIQUE (issuer, subject)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE access.sessions (
            id UUID PRIMARY KEY,
            session_token_hash TEXT NOT NULL UNIQUE,
            user_id UUID NOT NULL REFERENCES access.users(id),
            csrf_token_hash TEXT NOT NULL,
            encrypted_refresh_token TEXT,
            encrypted_id_token TEXT,
            expires_at TIMESTAMPTZ NOT NULL,
            idle_expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            revoked_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE access.login_attempts (
            id UUID PRIMARY KEY,
            state TEXT NOT NULL UNIQUE,
            nonce TEXT NOT NULL,
            code_verifier TEXT NOT NULL,
            redirect_uri TEXT NOT NULL,
            return_to TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            consumed_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE access.tenants (
            id UUID PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE access.memberships (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES access.tenants(id),
            user_id UUID NOT NULL REFERENCES access.users(id),
            role TEXT NOT NULL CHECK (role IN ('admin', 'sales', 'warehouse', 'viewer')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_access_memberships_user_tenant UNIQUE (user_id, tenant_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_access_memberships_tenant ON access.memberships (tenant_id)")
    op.execute("CREATE INDEX ix_access_sessions_user ON access.sessions (user_id)")

    # Grants for runtime role
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE ON
          access.users, access.sessions, access.login_attempts,
          access.tenants, access.memberships
        TO stockpilot_app
        """
    )

    # RLS: users/sessions/login_attempts are not tenant commercial tables.
    # Memberships: a user may read their own rows before selecting a tenant.
    op.execute("ALTER TABLE access.memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE access.memberships FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY memberships_select_own ON access.memberships
          FOR SELECT TO stockpilot_app
          USING (user_id::text = NULLIF(current_setting('app.user_id', true), ''))
        """
    )
    op.execute(
        """
        CREATE POLICY memberships_write_admin ON access.memberships
          FOR ALL TO stockpilot_app
          USING (
            tenant_id::text = NULLIF(current_setting('app.tenant_id', true), '')
            AND NULLIF(current_setting('app.role', true), '') = 'admin'
          )
          WITH CHECK (
            tenant_id::text = NULLIF(current_setting('app.tenant_id', true), '')
            AND NULLIF(current_setting('app.role', true), '') = 'admin'
          )
        """
    )

    op.execute("ALTER TABLE access.tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE access.tenants FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenants_select_member ON access.tenants
          FOR SELECT TO stockpilot_app
          USING (
            id::text = NULLIF(current_setting('app.tenant_id', true), '')
            OR EXISTS (
              SELECT 1 FROM access.memberships m
              WHERE m.tenant_id = access.tenants.id
                AND m.user_id::text = NULLIF(current_setting('app.user_id', true), '')
            )
          )
        """
    )
    # Ops bootstrap uses the migrator role (FORCE RLS still applies to table owners).
    op.execute(
        """
        CREATE POLICY tenants_migrator_all ON access.tenants
          FOR ALL TO stockpilot_migrator
          USING (true) WITH CHECK (true)
        """
    )
    op.execute(
        """
        CREATE POLICY memberships_migrator_all ON access.memberships
          FOR ALL TO stockpilot_migrator
          USING (true) WITH CHECK (true)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON access.users TO stockpilot_migrator")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON access.tenants, access.memberships TO stockpilot_migrator"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS access.memberships CASCADE")
    op.execute("DROP TABLE IF EXISTS access.tenants CASCADE")
    op.execute("DROP TABLE IF EXISTS access.login_attempts CASCADE")
    op.execute("DROP TABLE IF EXISTS access.sessions CASCADE")
    op.execute("DROP TABLE IF EXISTS access.users CASCADE")
