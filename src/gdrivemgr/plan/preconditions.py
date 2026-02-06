"""Precondition helpers (modified_time only, v1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from gdrivemgr.errors import ConflictError
from gdrivemgr.models import FileInfo
from gdrivemgr.util.time import same_instant

from .actions import Action
from .operation import PlanOperation

PRECONDITION_ACTIONS: set[Action] = {
    Action.RENAME,
    Action.MOVE,
    Action.TRASH,
    Action.DELETE_PERMANENT,
    Action.COPY,
    Action.DOWNLOAD_FILE,
}


def build_modified_time_precondition(modified_time: datetime) -> dict[str, Any]:
    """Build a modified_time-only precondition dict."""
    return {"expected_modified_time": modified_time}


def apply_default_preconditions(
    operations: list[PlanOperation],
    file_by_local_id: dict[str, FileInfo],
) -> None:
    """
    Apply default preconditions to operations in-place.

    Precondition is attached when:
        - action is in PRECONDITION_ACTIONS
        - target_local_id exists
        - target has modified_time
    """
    for op in operations:
        if op.action not in PRECONDITION_ACTIONS:
            continue
        if not op.target_local_id:
            continue

        info = file_by_local_id.get(op.target_local_id)
        if not info or not info.modified_time:
            continue

        op.precondition = build_modified_time_precondition(info.modified_time)


def check_modified_time_precondition(
    precondition: dict[str, Any],
    actual_modified_time: Optional[datetime],
) -> None:
    """
    Check modified_time precondition.

    Raises:
        ConflictError: if actual_modified_time doesn't match expected.
    """
    expected = precondition.get("expected_modified_time")
    if not isinstance(expected, datetime):
        raise ConflictError("Invalid precondition: expected_modified_time missing")

    if actual_modified_time is None:
        raise ConflictError("Precondition failed: modified_time not available")

    if not same_instant(expected, actual_modified_time):
        raise ConflictError("Precondition failed: modified_time mismatch")
