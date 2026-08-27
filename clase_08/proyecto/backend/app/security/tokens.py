"""Opaque token generation and irreversible storage digests."""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
import secrets


class TokenCodec:
    def __init__(self, secret: str) -> None:
        self.secret = secret.encode()

    def issue(self) -> str:
        return secrets.token_urlsafe(32)

    def digest(self, token: str) -> str:
        return hmac.new(self.secret, token.encode(), hashlib.sha256).hexdigest()


@dataclass
class RecoveryToken:
    digest: str
    expires_at: datetime
    used_at: datetime | None = None

    def usable(self, now: datetime) -> bool:
        return self.used_at is None and now < self.expires_at

    def consume(self, now: datetime) -> "RecoveryToken":
        if self.usable(now):
            self.used_at = now
        return self
