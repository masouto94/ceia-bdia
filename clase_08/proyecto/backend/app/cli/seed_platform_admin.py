"""Seed, rotate, or disable one declarative platform administrator."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys

from sqlalchemy import create_engine, text

from app.core.config import AdminToolSettings
from app.security.password import hash_password


def _password() -> str:
    value = os.environ.get("PLATFORM_ADMIN_PASSWORD")
    if value:
        return value
    if not sys.stdin.isatty():
        value = sys.stdin.readline().rstrip("\n")
        if value:
            return value
        raise SystemExit("platform password input required")
    value = getpass.getpass("Platform administrator password: ")
    if not value:
        raise SystemExit("platform password input required")
    return value


def _email(args: argparse.Namespace) -> str:
    # Educational convenience: fall back to PLATFORM_ADMIN_EMAIL from the
    # environment (e.g. sourced from .env) so the command needs no argv.
    value = args.email or os.environ.get("PLATFORM_ADMIN_EMAIL")
    if not value:
        raise SystemExit("platform admin email required (--email or PLATFORM_ADMIN_EMAIL)")
    return value.lower()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--rotate", action="store_true")
    mode.add_argument("--disable", action="store_true")
    mode.add_argument("--inspect", action="store_true")
    args = parser.parse_args()
    email = _email(args)
    admin_settings = AdminToolSettings()  # pyright: ignore[reportCallIssue] -- environment supplies the migrator URL
    engine = create_engine(admin_settings.migrator_database_url, hide_parameters=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("SET ROLE project_owner"))
            if args.inspect:
                # Read-only lookup; never selects or prints password_hash or session/token material.
                row = connection.execute(text("""
                  SELECT u.email, u.credential_version, pa.enabled, u.created_at,
                         (SELECT count(*) FROM public.sessions s WHERE s.user_id = u.id AND s.revoked_at IS NULL AND s.expires_at > now()) AS active_sessions
                  FROM public.users u JOIN public.platform_admins pa ON pa.user_id = u.id
                  WHERE u.email = :email AND u.account_scope = 'platform'
                """), {"email": email}).mappings().first()
                if not row:
                    print(json.dumps({"found": False}))
                    return
                print(json.dumps({
                    "found": True,
                    "email": row["email"],
                    "enabled": bool(row["enabled"]),
                    "credential_version": int(row["credential_version"]),
                    "created_at": row["created_at"].isoformat(),
                    "active_sessions": int(row["active_sessions"]),
                }))
                return
            if args.disable:
                changed = connection.execute(text("""
                  UPDATE public.platform_admins pa SET enabled=false
                  FROM public.users u WHERE pa.user_id=u.id AND u.email=:email AND u.account_scope='platform'
                  RETURNING pa.user_id
                """), {"email": email}).scalar_one_or_none()
                if changed:
                    connection.execute(text("UPDATE public.sessions SET revoked_at=now() WHERE user_id=:id AND revoked_at IS NULL"), {"id": changed})
                    # Actor-less operator action; resource is the affected identity, never a raw email/error string.
                    connection.execute(text("""
                      INSERT INTO public.audit_events(id,actor_id,tenant_id,action,outcome,resource,metadata)
                      VALUES (gen_random_uuid(),NULL,NULL,'platform.admin_disabled','success',:resource,'{}'::jsonb)
                    """), {"resource": str(changed)})
                return
            existing = connection.execute(
                text("SELECT id FROM public.users WHERE email=:email AND account_scope='platform'"),
                {"email": email},
            ).scalar_one_or_none()
            if connection.execute(text("SELECT 1 FROM public.users WHERE email=:email AND account_scope <> 'platform'"), {"email": email}).scalar_one_or_none():
                raise SystemExit("email already belongs to a non-platform identity")
            if existing and not args.rotate:
                return
            password_hash = hash_password(_password())
            if existing:
                connection.execute(text("UPDATE public.users SET password_hash=:hash, credential_version=credential_version+1 WHERE id=:id AND account_scope='platform'"), {"hash": password_hash, "id": existing})
                connection.execute(text("UPDATE public.sessions SET revoked_at=now() WHERE user_id=:id AND revoked_at IS NULL"), {"id": existing})
                # Actor-less operator action; resource is the affected identity, never the raw password/hash.
                connection.execute(text("""
                  INSERT INTO public.audit_events(id,actor_id,tenant_id,action,outcome,resource,metadata)
                  VALUES (gen_random_uuid(),NULL,NULL,'platform.credential_rotated','success',:resource,'{}'::jsonb)
                """), {"resource": str(existing)})
                return
            user_id = connection.execute(text("SELECT gen_random_uuid()")).scalar_one()
            connection.execute(text("INSERT INTO public.users(id,email,password_hash,account_scope) VALUES(:id,:email,:hash,'platform')"), {"id": user_id, "email": email, "hash": password_hash})
            connection.execute(text("INSERT INTO public.platform_admins(user_id,account_scope,enabled) VALUES(:id,'platform',true)"), {"id": user_id})
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
