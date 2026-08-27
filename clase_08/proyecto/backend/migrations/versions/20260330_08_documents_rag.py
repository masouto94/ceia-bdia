"""Harden private documents and add fixed-dimension pgvector ingestion."""

from alembic import op  # pyright: ignore[reportMissingImports] -- resolved by the backend migration environment

revision = "20260330_08"
down_revision = "20260330_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
      CREATE EXTENSION IF NOT EXISTS vector;
      ALTER TABLE documents ADD COLUMN content_type varchar(32), ADD COLUMN size_bytes integer,
        ADD COLUMN sha256 char(64), ADD CONSTRAINT documents_status CHECK (ingestion_status IN ('pending','processing','ready','failed')),
        ADD CONSTRAINT documents_size CHECK (size_bytes > 0 AND size_bytes <= 26214400), ADD CONSTRAINT documents_tenant_id UNIQUE (tenant_id,id),
        ADD CONSTRAINT documents_tenant_key UNIQUE (tenant_id,object_key);
      ALTER TABLE documents ALTER COLUMN content_type SET NOT NULL, ALTER COLUMN size_bytes SET NOT NULL, ALTER COLUMN sha256 SET NOT NULL;
      ALTER TABLE chunks ADD COLUMN active boolean NOT NULL DEFAULT false,
        ADD CONSTRAINT chunks_tenant_id UNIQUE (tenant_id,id), DROP CONSTRAINT chunks_document_id_fkey,
        ADD CONSTRAINT chunks_document_tenant_fk FOREIGN KEY (tenant_id, document_id) REFERENCES documents(tenant_id,id) ON DELETE CASCADE,
        ADD CONSTRAINT chunks_ordinal_unique UNIQUE (tenant_id,document_id,ordinal,active);
      ALTER TABLE embeddings DROP CONSTRAINT embeddings_chunk_id_fkey;
      ALTER TABLE embeddings ALTER COLUMN embedding TYPE vector(8) USING embedding::text::vector;
      ALTER TABLE embeddings ADD CONSTRAINT embeddings_chunk_tenant_fk FOREIGN KEY (tenant_id,chunk_id) REFERENCES chunks(tenant_id,id) ON DELETE CASCADE,
        ADD CONSTRAINT embeddings_chunk_unique UNIQUE (tenant_id,chunk_id);
      CREATE INDEX embeddings_cosine_idx ON embeddings USING hnsw (embedding vector_cosine_ops);
      CREATE TABLE ingestion_runs (
        id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id), document_id uuid NOT NULL,
        status varchar(16) NOT NULL CHECK (status IN ('ready','failed')), chunk_count integer NOT NULL DEFAULT 0,
        error varchar(240), created_at timestamptz NOT NULL DEFAULT now(),
        FOREIGN KEY (tenant_id, document_id) REFERENCES documents(tenant_id,id)
      );
      ALTER TABLE ingestion_runs ENABLE ROW LEVEL SECURITY;
      ALTER TABLE ingestion_runs FORCE ROW LEVEL SECURITY;
      CREATE POLICY ingestion_runs_tenant_isolation ON ingestion_runs
        USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL)
        WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      GRANT SELECT,INSERT ON ingestion_runs TO app_runtime;
      GRANT DELETE ON chunks,embeddings TO app_runtime;
    """)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("DROP TABLE ingestion_runs; DROP INDEX embeddings_cosine_idx; ALTER TABLE embeddings ALTER COLUMN embedding TYPE jsonb USING to_jsonb(embedding::text); ALTER TABLE chunks DROP COLUMN active; ALTER TABLE documents DROP COLUMN content_type, DROP COLUMN size_bytes, DROP COLUMN sha256")
    op.execute("RESET ROLE")
