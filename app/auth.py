"""API key authentication and management."""

import hashlib
import os
import secrets

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import APIKey

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")


def hash_api_key(key: str) -> str:
    """Hash an API key using SHA-256 for secure storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return f"cnj_{secrets.token_urlsafe(32)}"


def verify_api_key(
    api_key: str = Security(API_KEY_HEADER),
    db: Session = Depends(get_db),
) -> APIKey:
    """Validate the provided API key against stored hashes.

    Raises:
        HTTPException: If the key is missing, invalid, or deactivated.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
        )

    key_hash = hash_api_key(api_key)
    db_key = (
        db.query(APIKey)
        .filter(APIKey.key_hash == key_hash, APIKey.is_active.is_(True))
        .first()
    )

    if not db_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or deactivated API key.",
        )

    return db_key


def verify_admin_secret(
    api_key: str = Security(API_KEY_HEADER),
) -> str:
    """Validate that the provided key matches the admin secret.

    The admin secret is used only for generating new API keys.

    Raises:
        HTTPException: If the admin secret is not configured or doesn't match.
    """
    if not ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin secret not configured on server.",
        )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing admin secret. Provide X-API-Key header.",
        )

    if not secrets.compare_digest(api_key, ADMIN_SECRET):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin secret.",
        )

    return api_key
