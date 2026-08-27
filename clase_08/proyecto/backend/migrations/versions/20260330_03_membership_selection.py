"""Allow a trusted authenticated user to verify only their own memberships before selection."""

# pyright: reportMissingImports=false

from alembic import op

revision = "20260330_03"
down_revision = "20260330_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""DO $$ BEGIN CREATE POLICY memberships_select_own ON memberships FOR SELECT USING (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid); EXCEPTION WHEN duplicate_object THEN NULL; END $$""")
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("DROP POLICY IF EXISTS memberships_select_own ON memberships")
    op.execute("RESET ROLE")
