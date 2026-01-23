"""Public error exports for gdrivemgr."""

from __future__ import annotations

from .exceptions import (
    ApiError,
    AuthError,
    ConflictError,
    GDriveMgrError,
    HttpErrorInfo,
    InvalidArgumentError,
    InvalidStateError,
    LocalValidationError,
    NetworkError,
    NotFoundError,
    PermissionError,
    QuotaExceededError,
    RateLimitError,
    map_http_error,
)

__all__ = [
    "GDriveMgrError",
    "LocalValidationError",
    "InvalidStateError",
    "AuthError",
    "PermissionError",
    "InvalidArgumentError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "QuotaExceededError",
    "NetworkError",
    "ApiError",
    "HttpErrorInfo",
    "map_http_error",
]
