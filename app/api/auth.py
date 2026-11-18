"""Inbound API-key authentication. Owner: DevOps 1 (app/api/).

Day 4 (lead instruction): the API should accept an API key in a header, read
from the environment and never committed, with the method configurable so it
can be switched to Bearer later without a code change.

    AUTH_METHOD=none      (default) - the endpoint stays open
    AUTH_METHOD=api_key   the caller sends `X-API-Key: <key>`
    AUTH_METHOD=bearer    the caller sends `Authorization: Bearer <token>`

Rules:
- the key is compared in constant time and is never logged, echoed back or
  written into an error body
- a missing key and a wrong key give the same 401, so the answer cannot be
  used to probe which keys exist
- GET /health stays open: a liveness probe cannot carry a credential, and the
  container HEALTHCHECK depends on it
"""
import secrets
from typing import Optional

from fastapi import HTTPException, Request

from app.config import get_settings

# Header names per method. Kept here so the contract is in one place.
API_KEY_HEADER = "X-API-Key"
BEARER_SCHEME = "bearer"


def _presented_key(request: Request, method: str) -> Optional[str]:
    """The credential the caller presented, or None."""
    if method == "api_key":
        return request.headers.get(API_KEY_HEADER) or None
    if method == "bearer":
        header = request.headers.get("Authorization") or ""
        scheme, _, token = header.partition(" ")
        if scheme.strip().lower() != BEARER_SCHEME:
            return None
        return token.strip() or None
    return None


def _reject(method: str) -> HTTPException:
    """The same 401 for every reason - missing, wrong or the wrong header."""
    headers = {"WWW-Authenticate": "Bearer"} if method == "bearer" else None
    return HTTPException(status_code=401, headers=headers)


def require_api_key(request: Request) -> None:
    """FastAPI dependency: 401 unless the caller presents the right key.

    Raises HTTPException(401) when AUTH_METHOD is on and the credential is
    missing or wrong. Does nothing when AUTH_METHOD is "none".
    """
    settings = get_settings()
    method = settings.auth_method
    if method == "none":
        return

    expected = settings.api_key or ""
    presented = _presented_key(request, method)
    # compare_digest keeps the comparison time independent of how many
    # characters match, so the endpoint cannot be used to guess the key.
    if not presented or not secrets.compare_digest(presented, expected):
        # Scope only: never log the header value or the expected key.
        raise _reject(method)
