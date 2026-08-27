#!/bin/sh
set -eu

for required in POSTGRES_PASSWORD PROJECT_MIGRATOR_PASSWORD APP_RUNTIME_PASSWORD AUTH_RUNTIME_PASSWORD ASSISTANT_READER_PASSWORD; do
    eval "value=\${$required-}"
    test -n "$value" || {
        echo "missing required database credential" >&2
        exit 1
    }
done
for left in POSTGRES_PASSWORD PROJECT_MIGRATOR_PASSWORD APP_RUNTIME_PASSWORD AUTH_RUNTIME_PASSWORD ASSISTANT_READER_PASSWORD; do
    eval "left_value=\${$left}"
    for right in POSTGRES_PASSWORD PROJECT_MIGRATOR_PASSWORD APP_RUNTIME_PASSWORD AUTH_RUNTIME_PASSWORD ASSISTANT_READER_PASSWORD; do
        test "$left" = "$right" && continue
        eval "right_value=\${$right}"
        test "$left_value" != "$right_value" || {
            echo "credential values must be pairwise distinct" >&2
            exit 1
        }
    done
done

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv project_migrator_password PROJECT_MIGRATOR_PASSWORD
\getenv app_runtime_password APP_RUNTIME_PASSWORD
\getenv auth_runtime_password AUTH_RUNTIME_PASSWORD
\getenv assistant_reader_password ASSISTANT_READER_PASSWORD
CREATE EXTENSION IF NOT EXISTS vector;
CREATE ROLE project_owner NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
CREATE ROLE session_issuer_owner NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
CREATE ROLE platform_read_owner NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
ALTER SCHEMA public OWNER TO project_owner;
SELECT format('CREATE ROLE project_migrator LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT PASSWORD %L', :'project_migrator_password'); \gexec
SELECT format('CREATE ROLE app_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT PASSWORD %L', :'app_runtime_password'); \gexec
SELECT format('CREATE ROLE auth_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT PASSWORD %L', :'auth_runtime_password'); \gexec
SELECT format('CREATE ROLE assistant_reader LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT PASSWORD %L', :'assistant_reader_password'); \gexec
GRANT USAGE, CREATE ON SCHEMA public TO project_migrator;
GRANT project_owner TO project_migrator WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
GRANT session_issuer_owner TO project_owner WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
GRANT platform_read_owner TO project_owner WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
SQL
