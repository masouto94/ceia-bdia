"""Mark admin-created accounts as requiring recovery password setup."""

# pyright: reportMissingImports=false

from alembic import op

revision = "20260330_04"
down_revision = "20260330_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("ALTER TABLE users ADD COLUMN password_setup_required boolean NOT NULL DEFAULT false")
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("ALTER TABLE users DROP COLUMN password_setup_required")
    op.execute("RESET ROLE")
