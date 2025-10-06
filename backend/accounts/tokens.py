"""Signed, expiring bearer tokens shared by HTTP requests and WebSockets."""
from django.conf import settings
from django.core import signing

SALT = "accounts.token"


def issue_token(role: str, subject: int) -> str:
    return signing.dumps({"role": role, "sub": subject}, salt=SALT)


def read_token(token, role: str):
    """Return the subject id, or None if the token is invalid, expired, or for another role."""
    if not isinstance(token, str):
        return None
    try:
        data = signing.loads(token, salt=SALT, max_age=settings.TOKEN_MAX_AGE_SECONDS)
    except signing.BadSignature:
        return None
    return data["sub"] if data.get("role") == role else None
