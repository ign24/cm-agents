"""Security utilities for API."""

import re
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from .config import settings

# Slug validation pattern: only lowercase letters, numbers, and hyphens
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")

# Allowed file extensions for logo/assets
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


def validate_slug(slug: str) -> bool:
    """
    Validate that a slug is safe (no path traversal).

    Valid slugs:
    - Only lowercase letters, numbers, hyphens
    - Must start and end with alphanumeric
    - No consecutive hyphens
    - Length 1-64 characters
    """
    if not slug or len(slug) > 64:
        return False

    if ".." in slug or "/" in slug or "\\" in slug:
        return False

    return bool(SLUG_PATTERN.match(slug))


def safe_slug(slug: str) -> str:
    """
    Validate slug and return it, or raise HTTPException.

    Use as a dependency in routes that accept slugs.
    """
    if not validate_slug(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid slug: '{slug}'. Only lowercase letters, numbers, and hyphens allowed.",
        )
    return slug


def validate_file_extension(filename: str, allowed: set[str] | None = None) -> bool:
    """Validate file has allowed extension."""
    if allowed is None:
        allowed = ALLOWED_IMAGE_EXTENSIONS

    if not filename:
        return False

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in allowed


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self._requests: dict[str, list[float]] = {}

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
        # Use X-Forwarded-For if behind proxy, otherwise use client host
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup_old_requests(self, client_id: str, now: float) -> None:
        """Remove requests older than 1 minute."""
        if client_id in self._requests:
            cutoff = now - 60
            self._requests[client_id] = [t for t in self._requests[client_id] if t > cutoff]

    def is_rate_limited(self, request: Request) -> bool:
        """Check if request should be rate limited."""
        import time

        now = time.time()
        client_id = self._get_client_id(request)

        self._cleanup_old_requests(client_id, now)

        if client_id not in self._requests:
            self._requests[client_id] = []

        if len(self._requests[client_id]) >= self.requests_per_minute:
            return True

        self._requests[client_id].append(now)
        return False


# Global rate limiter instance
rate_limiter = RateLimiter(requests_per_minute=120)


async def check_rate_limit(request: Request) -> None:
    """Dependency to check rate limit."""
    if rate_limiter.is_rate_limited(request):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down.",
        )


async def verify_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> str | None:
    """
    Verify API key if configured.

    If API_KEY is not set in settings, all requests are allowed.
    If API_KEY is set, requests must include matching X-API-Key header.
    """
    required_key = getattr(settings, "API_KEY", None)

    if not required_key:
        # No API key configured, allow all
        return None

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not secrets.compare_digest(x_api_key, required_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return x_api_key


# Type alias for dependency injection
RateLimitDep = Annotated[None, Depends(check_rate_limit)]
ApiKeyDep = Annotated[str | None, Depends(verify_api_key)]
