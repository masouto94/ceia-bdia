"""Invalidate incompatible fixtures and move embeddings from vector(8) to vector(384)."""
from alembic import op  # pyright: ignore[reportMissingImports]

revision = "20260330_10"
down_revision = "20260330_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        DROP INDEX IF EXISTS embeddings_cosine_idx;
        DELETE FROM embeddings;
        UPDATE chunks SET active=false WHERE active=true;
        UPDATE documents SET ingestion_status='pending' WHERE ingestion_status IN ('ready','processing');
        ALTER TABLE embeddings ALTER COLUMN embedding TYPE vector(384);
        CREATE INDEX embeddings_cosine_idx ON embeddings USING hnsw (embedding vector_cosine_ops);
    """)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        DROP INDEX IF EXISTS embeddings_cosine_idx;
        DELETE FROM embeddings;
        UPDATE chunks SET active=false WHERE active=true;
        UPDATE documents SET ingestion_status='pending' WHERE ingestion_status IN ('ready','processing');
        ALTER TABLE embeddings ALTER COLUMN embedding TYPE vector(8);
        CREATE INDEX embeddings_cosine_idx ON embeddings USING hnsw (embedding vector_cosine_ops);
    """)
    op.execute("RESET ROLE")
