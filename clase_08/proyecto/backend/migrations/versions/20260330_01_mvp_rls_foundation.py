"""Create the target-owned multi-tenant MVP foundation."""

# pyright: reportMissingImports=false

from alembic import op

revision = "20260330_01"
down_revision = None
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "tenants", "memberships", "roles", "role_permissions", "experiments",
    "results", "metrics", "documents", "chunks", "embeddings",
)


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        CREATE TABLE users (
            id uuid PRIMARY KEY, email varchar(320) UNIQUE NOT NULL,
            password_hash varchar(255) NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE tenants (
            id uuid PRIMARY KEY, name varchar(120) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE memberships (
            tenant_id uuid NOT NULL REFERENCES tenants(id), user_id uuid NOT NULL REFERENCES users(id),
            active boolean NOT NULL DEFAULT true, PRIMARY KEY (tenant_id, user_id)
        );
        CREATE TABLE roles (
            id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id),
            name varchar(32) NOT NULL, UNIQUE (tenant_id, name)
        );
        CREATE TABLE permissions (code varchar(64) PRIMARY KEY);
        CREATE TABLE role_permissions (
            tenant_id uuid NOT NULL REFERENCES tenants(id), role_id uuid NOT NULL REFERENCES roles(id),
            permission_code varchar(64) NOT NULL REFERENCES permissions(code),
            PRIMARY KEY (tenant_id, role_id, permission_code)
        );
        CREATE TABLE experiments (
            id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id),
            creator_id uuid NOT NULL REFERENCES users(id), name varchar(200) NOT NULL,
            status varchar(16) NOT NULL CHECK (status IN ('draft', 'running', 'completed', 'failed'))
        );
        CREATE TABLE results (
            id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id),
            experiment_id uuid NOT NULL REFERENCES experiments(id), creator_id uuid NOT NULL REFERENCES users(id),
            status varchar(16) NOT NULL, summary text
        );
        CREATE TABLE metrics (
            id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id),
            result_id uuid NOT NULL REFERENCES results(id), name varchar(120) NOT NULL,
            value_type varchar(16) NOT NULL CHECK (value_type IN ('number', 'text', 'boolean', 'json')),
            number_value integer, text_value text, boolean_value boolean, json_value jsonb
        );
        CREATE TABLE documents (
            id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id),
            created_by uuid NOT NULL REFERENCES users(id), name varchar(255) NOT NULL,
            object_key varchar(255) NOT NULL, ingestion_status varchar(16) NOT NULL
        );
        CREATE TABLE chunks (
            id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id),
            document_id uuid NOT NULL REFERENCES documents(id), content text NOT NULL, ordinal integer NOT NULL
        );
        CREATE TABLE embeddings (
            id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id),
            chunk_id uuid NOT NULL REFERENCES chunks(id), embedding jsonb NOT NULL
        );
    """)
    for table in TENANT_TABLES:
        tenant_column = "id" if table == "tenants" else "tenant_id"
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query -- table comes from TENANT_TABLES
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query -- table comes from TENANT_TABLES
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query -- identifiers come from TENANT_TABLES
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (
                {tenant_column} = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                AND NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
            )
            WITH CHECK (
                {tenant_column} = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                AND NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
            )
        """)
    op.execute("GRANT USAGE ON SCHEMA public TO app_runtime, assistant_reader")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON users, tenants, memberships, roles, permissions, "
        "role_permissions, experiments, results, metrics, documents, chunks, embeddings TO app_runtime"
    )
    op.execute("GRANT SELECT ON experiments, results, metrics, documents, chunks, embeddings TO assistant_reader")
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    for table in reversed(TENANT_TABLES):
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query -- table comes from TENANT_TABLES
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP TABLE permissions")
    op.execute("DROP TABLE users")
    op.execute("RESET ROLE")
