"""Private post-password session issuance through the isolated auth pool."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import text

from app.core.config import settings
from app.core.database import AuthSessionLocal


class SessionIssueUnavailable(RuntimeError):
    """The bounded issuer must fail closed without exposing eligibility."""


def register_tenant_bootstrap(
    user_id: UUID, tenant_id: UUID, role_ids: dict[str, UUID], email: str, password_hash: str, tenant_name: str,
) -> None:
    """Create only a fresh tenant and its first administrator through auth_runtime."""
    session = None
    try:
        session = AuthSessionLocal()
        with session.begin():
            session.execute(
                text("""SELECT public.register_tenant_bootstrap(
                    :user_id,:tenant_id,:admin_id,:member_id,:viewer_id,:email,:password_hash,:tenant_name
                )"""),
                {
                    "user_id": user_id, "tenant_id": tenant_id, "admin_id": role_ids["admin"],
                    "member_id": role_ids["member"], "viewer_id": role_ids["viewer"],
                    "email": email, "password_hash": password_hash, "tenant_name": tenant_name,
                },
            )
    except Exception as exc:
        raise SessionIssueUnavailable("tenant registration unavailable") from exc
    finally:
        if session is not None:
            session.close()


def issue_platform_session(user_id: UUID, credential_version: int, token_digest: str, csrf_digest: str) -> None:
    """Call the isolated issuer for an enabled declarative platform administrator."""
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.session_ttl_minutes)
    session = None
    try:
        session = AuthSessionLocal()
        with session.begin():
            session.execute(
                text("SELECT public.issue_platform_session(:id,:version,:token,:csrf,:expires)"),
                {"id": user_id, "version": credential_version, "token": token_digest, "csrf": csrf_digest, "expires": expires_at},
            )
    except Exception as exc:
        raise SessionIssueUnavailable("platform session issuance unavailable") from exc
    finally:
        if session is not None:
            session.close()


def issue_tenant_session(user_id: UUID, credential_version: int, token_digest: str, csrf_digest: str) -> None:
    """Call only after password verification; the database revalidates every input."""
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.session_ttl_minutes)
    session = None
    try:
        session = AuthSessionLocal()
        with session.begin():
            session.execute(
                text("SELECT public.issue_tenant_session(:id,:version,:token,:csrf,:expires)"),
                {"id": user_id, "version": credential_version, "token": token_digest, "csrf": csrf_digest, "expires": expires_at},
            )
    except Exception as exc:
        raise SessionIssueUnavailable("session issuance unavailable") from exc
    finally:
        if session is not None:
            session.close()

