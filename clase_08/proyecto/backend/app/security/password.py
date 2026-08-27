"""Small stdlib password hashing boundary for the demo."""

import base64
import hashlib
import hmac
import secrets

_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("password must contain at least 8 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(_ITERATIONS, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$")
        actual = hashlib.pbkdf2_hmac(algorithm.removeprefix("pbkdf2_"), password.encode(), base64.b64decode(salt), int(rounds))
        return hmac.compare_digest(actual, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False
