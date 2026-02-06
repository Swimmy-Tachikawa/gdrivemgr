"""gdrivemgr public API."""

from __future__ import annotations

from gdrivemgr.auth import AuthInfo, OAuthClient
from gdrivemgr.errors import (
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
from gdrivemgr.local import GoogleDriveLocal
from gdrivemgr.manager import GoogleDriveManager
from gdrivemgr.models import FileInfo, OperationResult, SyncResult
from gdrivemgr.plan import Action, PlanOperation, SyncPlan

__all__ = [
    # High-level
    "GoogleDriveManager",
    "GoogleDriveLocal",
    # Auth
    "AuthInfo",
    "OAuthClient",
    # Plan / Models
    "Action",
    "PlanOperation",
    "SyncPlan",
    "FileInfo",
    "OperationResult",
    "SyncResult",
    # Errors
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
