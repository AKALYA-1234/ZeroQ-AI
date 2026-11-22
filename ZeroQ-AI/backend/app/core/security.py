from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt  # PyJWT (python-jose is unmaintained and has an unpatched advisory)

# Tolerated clock difference between the host that issued a token and the one validating it
# (VM clock steps, several hosts behind a load balancer). Applies to iat and exp.
CLOCK_SKEW_LEEWAY_SECONDS = 30
import bcrypt
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pw_bytes = plain_password.encode('utf-8')[:72]
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    pw_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Optional[dict]:
    try:
        # Only the configured algorithm is accepted (no "none", no algorithm confusion); exp is required.
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
                          options={"require": ["exp", "sub"]}, leeway=CLOCK_SKEW_LEEWAY_SECONDS)
    except jwt.PyJWTError:
        return None


PASSWORD_MIN_LENGTH = 8


def password_policy_error(password: str):
    """Return a human-readable reason if the password is too weak, else None."""
    if len(password or "") < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        return "Password must contain both letters and numbers"
    return None
