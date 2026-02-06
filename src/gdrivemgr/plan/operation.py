"""Plan operation model (explicit fields; no args dict)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .actions import Action


@dataclass(slots=True)
class PlanOperation:
    """
    A single operation within a SyncPlan.

    This is an explicit-field model (no generic args dict) by spec.
    """

    op_id: str
    seq: int
    action: Action

    precondition: Optional[dict[str, Any]] = None
    note: Optional[str] = None

    target_local_id: Optional[str] = None
    parent_local_id: Optional[str] = None
    new_parent_local_id: Optional[str] = None
    result_local_id: Optional[str] = None

    name: Optional[str] = None
    local_path: Optional[str] = None
    overwrite: Optional[bool] = None

    def validate_required_fields(self) -> None:
        """Validate required fields according to action. Raises ValueError."""
        if self.action is Action.CREATE_FOLDER:
            _require(self.parent_local_id, "parent_local_id")
            _require(self.name, "name")
            _require(self.result_local_id, "result_local_id")
            return

        if self.action is Action.COPY:
            _require(self.target_local_id, "target_local_id")
            _require(self.new_parent_local_id, "new_parent_local_id")
            _require(self.result_local_id, "result_local_id")
            return

        if self.action is Action.RENAME:
            _require(self.target_local_id, "target_local_id")
            _require(self.name, "name")
            return

        if self.action is Action.MOVE:
            _require(self.target_local_id, "target_local_id")
            _require(self.new_parent_local_id, "new_parent_local_id")
            return

        if self.action in (Action.TRASH, Action.DELETE_PERMANENT):
            _require(self.target_local_id, "target_local_id")
            return

        if self.action is Action.UPLOAD_FILE:
            _require(self.parent_local_id, "parent_local_id")
            _require(self.local_path, "local_path")
            _require(self.result_local_id, "result_local_id")
            return

        if self.action is Action.DOWNLOAD_FILE:
            _require(self.target_local_id, "target_local_id")
            _require(self.local_path, "local_path")
            return

        raise ValueError(f"Unsupported action: {self.action}")


def _require(value: object, field_name: str) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"Missing required field: {field_name}")
