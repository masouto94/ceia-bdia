"""Alembic environment for fresh target-owned metadata only."""

# pyright: reportMissingImports=false

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import AdminToolSettings

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = None


def migration_url() -> str:
    return AdminToolSettings().migrator_database_url.replace(  # pyright: ignore[reportCallIssue] -- environment supplies migrator-only settings
        "postgresql+asyncpg://", "postgresql+psycopg://"
    )


def run_migrations_offline() -> None:
    context.configure(
        url=migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(migration_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
