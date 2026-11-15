"""Add monotonic seq to platform.audit_log for deterministic timeline order.

Revision ID: 0008_audit_log_seq
Revises: 0007_idempotency_outbox
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_audit_log_seq"
down_revision: str | None = "0007_idempotency_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # GENERATED ALWAYS AS IDENTITY backfills existing rows from the sequence.
    op.execute(
        """
        ALTER TABLE platform.audit_log
          ADD COLUMN seq BIGINT GENERATED ALWAYS AS IDENTITY
        """
    )
    # Timeline reads filter by tenant + entity and order by seq.
    op.execute(
        """
        CREATE INDEX ix_audit_log_tenant_entity_seq
          ON platform.audit_log (tenant_id, entity_type, entity_id, seq)
        """
    )
    # Runtime INSERT omits seq; identity still needs USAGE on the backing sequence.
    op.execute(
        """
        GRANT USAGE, SELECT ON SEQUENCE platform.audit_log_seq_seq TO stockpilot_app
        """
    )
    op.execute(
        """
        GRANT USAGE, SELECT ON SEQUENCE platform.audit_log_seq_seq TO stockpilot_migrator
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS platform.ix_audit_log_tenant_entity_seq")
    op.execute("ALTER TABLE platform.audit_log DROP COLUMN IF EXISTS seq")
