"""Add failed_jobs replay columns and sanitized_envelope.

Revision ID: 0012_failed_jobs_replay
Revises: 0011_inbox_notifications
Create Date: 2026-11-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012_failed_jobs_replay"
down_revision: str | None = "0011_inbox_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE platform.failed_jobs
          ADD COLUMN sanitized_envelope JSONB,
          ADD COLUMN replayed_at TIMESTAMPTZ,
          ADD COLUMN replayed_by TEXT,
          ADD COLUMN replay_count INTEGER NOT NULL DEFAULT 0
            CHECK (replay_count >= 0)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_failed_jobs_unreplayed
          ON platform.failed_jobs (last_failed_at DESC)
          WHERE replayed_at IS NULL
        """
    )
    # stockpilot_app: no new rights (0011 INSERT-only still covers new INSERT columns).
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE ON platform.failed_jobs
          TO stockpilot_migrator
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS platform.ix_failed_jobs_unreplayed")
    op.execute(
        """
        ALTER TABLE platform.failed_jobs
          DROP COLUMN IF EXISTS sanitized_envelope,
          DROP COLUMN IF EXISTS replayed_at,
          DROP COLUMN IF EXISTS replayed_by,
          DROP COLUMN IF EXISTS replay_count
        """
    )
