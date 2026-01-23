"""Exception hierarchy and HTTP error mapping for gdrivemgr."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


class GDriveMgrError(Exception):
    """
    Base exception for gdrivemgr.

    Attributes:
        details: Optional structured information (e.g., HTTP status, reason).
        cause: Optional original exception that triggered this error.
    """

    def __init__(
        self,
        message: str,
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.details = details or {}
        self.cause = cause


class LocalValidationError(GDriveMgrError):
    """Raised when GoogleDriveLocal strict validation fails."""


class InvalidStateError(GDriveMgrError):
    """Raised when the library is used in an invalid state (e.g., open not called)."""


class AuthError(GDriveMgrError):
    """Raised when OAuth authentication/refresh fails."""


class PermissionError(GDriveMgrError):
    """Raised when access is denied (HTTP 403 non-quota)."""


class InvalidArgumentError(GDriveMgrError):
    """Raised when request arguments are invalid (HTTP 400, etc.)."""


class NotFoundError(GDriveMgrError):
    """Raised when a Drive resource is not found (HTTP 404)."""


class ConflictError(GDriveMgrError):
    """Raised when a conflict occurs (HTTP 409/412, precondition mismatch)."""


class RateLimitError(GDriveMgrError):
    """Raised when rate-limited (HTTP 429)."""


class QuotaExceededError(GDriveMgrError):
    """Raised when quota is exceeded (HTTP 403 with quota-related reason)."""


class NetworkError(GDriveMgrError):
    """Raised when network/timeout issues prevent the request."""


class ApiError(GDriveMgrError):
    """Raised for unclassified API errors (5xx, unknown 4xx, etc.)."""


@dataclass(frozen=True)
class HttpErrorInfo:
    """Lightweight HTTP error information for mapping to gdrivemgr exceptions."""

    status_code: int
    reason: str | None = None
    message: str | None = None
    details: dict[str, Any] | None = None


_QUOTA_REASON_KEYWORDS: tuple[str, ...] = (
    "quota",
    "rateLimitExceeded",
    "userRateLimitExceeded",
    "dailyLimitExceeded",
    "usageLimits",
    "storageQuotaExceeded",
)


def _is_quota_reason(reason: str | None) -> bool:
    if not reason:
        return False
    return any(key.lower() in reason.lower() for key in _QUOTA_REASON_KEYWORDS)


def map_http_error(
    info: HttpErrorInfo,
    *,
    cause: Optional[BaseException] = None,
) -> GDriveMgrError:
    """
    Map an HTTP error to a gdrivemgr exception.

    Policy (fixed by spec):
        - 401 -> AuthError
        - 403 -> PermissionError (default), but QuotaExceededError if quota-related
        - 404 -> NotFoundError
        - 409/412 -> ConflictError
        - 429 -> RateLimitError
        - 400 -> InvalidArgumentError
        - 5xx -> ApiError
        - otherwise -> ApiError
    """
    details: dict[str, Any] = {
        "status_code": info.status_code,
        "reason": info.reason,
    }
    if info.details:
        details.update(info.details)

    message = info.message or f"HTTP error {info.status_code}"

    if info.status_code == 400:
        return InvalidArgumentError(message, details=details, cause=cause)
    if info.status_code == 401:
        return AuthError(message, details=details, cause=cause)
    if info.status_code == 403:
        if _is_quota_reason(info.reason):
            return QuotaExceededError(message, details=details, cause=cause)
        return PermissionError(message, details=details, cause=cause)
    if info.status_code == 404:
        return NotFoundError(message, details=details, cause=cause)
    if info.status_code in (409, 412):
        return ConflictError(message, details=details, cause=cause)
    if info.status_code == 429:
        return RateLimitError(message, details=details, cause=cause)
    if 500 <= info.status_code <= 599:
        return ApiError(message, details=details, cause=cause)

    return ApiError(message, details=details, cause=cause)
