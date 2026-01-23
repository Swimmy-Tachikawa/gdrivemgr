"""Result models for apply/sync operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


OperationStatus = Literal["success", "failed", "skipped"]
SyncStatus = Literal["success", "failed"]


@dataclass(slots=True)
class OperationResult:
    """Result for a single operation (PlanOperation)."""

    op_id: str
    seq: int
    action: str
    status: OperationStatus

    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_details: Optional[dict[str, Any]] = None

    result_local_id: Optional[str] = None
    result_file_id: Optional[str] = None


@dataclass(slots=True)
class SyncResult:
    """Aggregate result for apply_plan/sync(execute=True)."""

    status: SyncStatus
    stopped_op_id: Optional[str]
    results: list[OperationResult]

    id_map: dict[str, str] = field(default_factory=dict)
    summary: dict[str, int] = field(default_factory=dict)
    snapshot_refreshed: bool = True
