"""GoogleDriveLocal: in-memory state + operation planning (no external I/O)."""

from __future__ import annotations

import copy
import os
from collections import deque
from datetime import datetime
from typing import Optional

from gdrivemgr.errors import LocalValidationError
from gdrivemgr.models import FileInfo
from gdrivemgr.plan import (
    Action,
    PlanOperation,
    SyncPlan,
    apply_default_preconditions,
    build_apply_order,
)
from gdrivemgr.util.ids import new_local_id, new_op_id, new_plan_id
from gdrivemgr.util.mime import FOLDER_MIME, is_folder
from gdrivemgr.util.time import now_utc

from .snapshot import DriveSnapshot
from .validators import (
    validate_exists,
    validate_is_folder,
    validate_move_no_cycle,
    validate_move_single_parent,
    validate_not_root,
    validate_not_tombstoned,
)


class GoogleDriveLocal:
    """
    Local, in-memory view of a Drive subtree (root scope) + planned operations.

    This class does NOT manipulate local PC filesystems as a "local mirror".
    It only records operations (PlanOperation) and maintains a virtual state
    for strict validation.
    """

    def __init__(self, root_local_id: str, snapshot: DriveSnapshot) -> None:
        self.root_local_id = root_local_id
        self._base_snapshot = snapshot.clone()
        self._snapshot = snapshot.clone()
        self._ops: list[PlanOperation] = []
        self._tombstoned: set[str] = set()

    @classmethod
    def from_file_infos(
        cls,
        root_local_id: str,
        file_infos: list[FileInfo],
    ) -> GoogleDriveLocal:
        snap = DriveSnapshot.from_file_infos(file_infos)
        return cls(root_local_id=root_local_id, snapshot=snap)

    # ----------------------------
    # Read APIs
    # ----------------------------
    def get(self, local_id: str) -> FileInfo:
        validate_exists(self._snapshot, local_id, "Item")
        return self._snapshot.get(local_id)

    def find_by_file_id(self, file_id: str) -> Optional[FileInfo]:
        """
        Find FileInfo by Drive file_id within the managed root scope.

        Spec decision:
            - Return only if the file_id is within the snapshot scope.
            - Do NOT fetch from Drive (no controller access).
        """
        if not self._snapshot.has(file_id):
            return None
        info = self._snapshot.get(file_id)
        if info.file_id == file_id or info.local_id == file_id:
            return info
        return None

    def list_children(self, parent_local_id: str) -> list[FileInfo]:
        validate_exists(self._snapshot, parent_local_id, "Parent")
        validate_is_folder(self._snapshot, parent_local_id, "Parent")

        ids = self._snapshot.list_children_ids(parent_local_id)
        infos = [self._snapshot.get(cid) for cid in ids]
        infos.sort(key=lambda x: (x.name, x.local_id))
        return infos

    def find_by_name(self, name: str, parent_local_id: Optional[str] = None) -> list[FileInfo]:
        """
        Find items by name.

        Spec decision:
            - If parent_local_id is None: search whole scope (root subtree).
            - Name uniqueness is NOT enforced; returns possibly multiple results.
        """
        if parent_local_id is not None:
            validate_exists(self._snapshot, parent_local_id, "Parent")
            name_map = self._snapshot.name_index_by_parent_local_id.get(parent_local_id, {})
            ids = name_map.get(name, [])
            return [self._snapshot.get(cid) for cid in ids]

        # Whole scope: traverse from root to avoid accidental inclusion of
        # unreachable nodes (shouldn't happen, but safe).
        matches: list[FileInfo] = []
        visited: set[str] = set()
        q: deque[str] = deque([self.root_local_id])

        while q:
            cur = q.popleft()
            if cur in visited:
                continue
            visited.add(cur)

            if not self._snapshot.has(cur):
                continue

            info = self._snapshot.get(cur)
            if info.name == name:
                matches.append(info)

            for child_id in self._snapshot.children_by_parent_local_id.get(cur, set()):
                if child_id not in visited:
                    q.append(child_id)

        matches.sort(key=lambda x: (x.name, x.local_id))
        return matches

    def list_ops(self) -> list[PlanOperation]:
        return list(self._ops)

    # ----------------------------
    # Operation planning APIs
    # ----------------------------
    def clear_ops(self) -> None:
        """Clear pending operations and reset virtual state to the base snapshot."""
        self._ops.clear()
        self._tombstoned.clear()
        self._snapshot = self._base_snapshot.clone()

    def create_folder(self, name: str, parent_local_id: str) -> str:
        validate_exists(self._snapshot, parent_local_id, "Parent")
        validate_is_folder(self._snapshot, parent_local_id, "Parent")
        validate_not_tombstoned(self._tombstoned, parent_local_id, "Parent")

        new_id = new_local_id()
        info = FileInfo(
            local_id=new_id,
            file_id=None,
            name=name,
            mime_type=FOLDER_MIME,
            parents=[parent_local_id],
        )
        self._snapshot.add_file(info)

        op = PlanOperation(
            op_id=new_op_id(),
            seq=self._next_seq(),
            action=Action.CREATE_FOLDER,
            parent_local_id=parent_local_id,
            name=name,
            result_local_id=new_id,
        )
        op.validate_required_fields()
        self._ops.append(op)
        return new_id

    def rename(self, target_local_id: str, new_name: str) -> None:
        validate_exists(self._snapshot, target_local_id, "Target")
        validate_not_root(self.root_local_id, target_local_id, "RENAME")
        validate_not_tombstoned(self._tombstoned, target_local_id, "Target")

        self._snapshot.rename(target_local_id, new_name)

        op = PlanOperation(
            op_id=new_op_id(),
            seq=self._next_seq(),
            action=Action.RENAME,
            target_local_id=target_local_id,
            name=new_name,
        )
        op.validate_required_fields()
        self._ops.append(op)

    def move(self, target_local_id: str, new_parent_local_id: str) -> None:
        validate_exists(self._snapshot, target_local_id, "Target")
        validate_exists(self._snapshot, new_parent_local_id, "New parent")
        validate_is_folder(self._snapshot, new_parent_local_id, "New parent")

        validate_not_root(self.root_local_id, target_local_id, "MOVE")
        validate_not_tombstoned(self._tombstoned, target_local_id, "Target")
        validate_not_tombstoned(self._tombstoned, new_parent_local_id, "New parent")

        validate_move_single_parent(self._snapshot, target_local_id)
        validate_move_no_cycle(self._snapshot, target_local_id, new_parent_local_id)

        self._snapshot.replace_parent(target_local_id, new_parent_local_id)

        op = PlanOperation(
            op_id=new_op_id(),
            seq=self._next_seq(),
            action=Action.MOVE,
            target_local_id=target_local_id,
            new_parent_local_id=new_parent_local_id,
        )
        op.validate_required_fields()
        self._ops.append(op)

    def copy(
        self,
        target_local_id: str,
        new_parent_local_id: str,
        new_name: Optional[str] = None,
    ) -> str:
        validate_exists(self._snapshot, target_local_id, "Target")
        validate_exists(self._snapshot, new_parent_local_id, "New parent")
        validate_is_folder(self._snapshot, new_parent_local_id, "New parent")

        validate_not_tombstoned(self._tombstoned, target_local_id, "Target")
        validate_not_tombstoned(self._tombstoned, new_parent_local_id, "New parent")

        src = self._snapshot.get(target_local_id)
        if is_folder(src.mime_type):
            raise LocalValidationError("Folder COPY is not supported in v1")

        copy_name = new_name if new_name is not None else src.name
        new_id = new_local_id()
        info = FileInfo(
            local_id=new_id,
            file_id=None,
            name=copy_name,
            mime_type=src.mime_type,
            parents=[new_parent_local_id],
        )
        self._snapshot.add_file(info)

        op = PlanOperation(
            op_id=new_op_id(),
            seq=self._next_seq(),
            action=Action.COPY,
            target_local_id=target_local_id,
            new_parent_local_id=new_parent_local_id,
            result_local_id=new_id,
            name=new_name,
        )
        op.validate_required_fields()
        self._ops.append(op)
        return new_id

    def trash(self, target_local_id: str) -> None:
        validate_exists(self._snapshot, target_local_id, "Target")
        validate_not_root(self.root_local_id, target_local_id, "TRASH")
        validate_not_tombstoned(self._tombstoned, target_local_id, "Target")

        self._tombstoned.add(target_local_id)
        self._snapshot.get(target_local_id).trashed = True

        op = PlanOperation(
            op_id=new_op_id(),
            seq=self._next_seq(),
            action=Action.TRASH,
            target_local_id=target_local_id,
        )
        op.validate_required_fields()
        self._ops.append(op)

    def delete_permanently(self, target_local_id: str) -> None:
        validate_exists(self._snapshot, target_local_id, "Target")
        validate_not_root(self.root_local_id, target_local_id, "DELETE_PERMANENT")
        validate_not_tombstoned(self._tombstoned, target_local_id, "Target")

        self._tombstoned.add(target_local_id)
        self._snapshot.get(target_local_id).trashed = True

        op = PlanOperation(
            op_id=new_op_id(),
            seq=self._next_seq(),
            action=Action.DELETE_PERMANENT,
            target_local_id=target_local_id,
        )
        op.validate_required_fields()
        self._ops.append(op)

    def upload_file(
        self,
        local_path: str,
        parent_local_id: str,
        name: Optional[str] = None,
    ) -> str:
        validate_exists(self._snapshot, parent_local_id, "Parent")
        validate_is_folder(self._snapshot, parent_local_id, "Parent")
        validate_not_tombstoned(self._tombstoned, parent_local_id, "Parent")

        file_name = name if name is not None else os.path.basename(local_path)
        new_id = new_local_id()
        info = FileInfo(
            local_id=new_id,
            file_id=None,
            name=file_name,
            mime_type="application/octet-stream",
            parents=[parent_local_id],
        )
        self._snapshot.add_file(info)

        op = PlanOperation(
            op_id=new_op_id(),
            seq=self._next_seq(),
            action=Action.UPLOAD_FILE,
            parent_local_id=parent_local_id,
            local_path=local_path,
            result_local_id=new_id,
            name=name,
        )
        op.validate_required_fields()
        self._ops.append(op)
        return new_id

    def download_file(
        self,
        target_local_id: str,
        local_path: str,
        overwrite: bool = False,
    ) -> None:
        validate_exists(self._snapshot, target_local_id, "Target")
        validate_not_tombstoned(self._tombstoned, target_local_id, "Target")

        op = PlanOperation(
            op_id=new_op_id(),
            seq=self._next_seq(),
            action=Action.DOWNLOAD_FILE,
            target_local_id=target_local_id,
            local_path=local_path,
            overwrite=overwrite,
        )
        op.validate_required_fields()
        self._ops.append(op)

    # ----------------------------
    # Plan building
    # ----------------------------
    def build_plan(self) -> SyncPlan:
        """
        Build a SyncPlan from current pending operations.

        Includes:
            - plan_id UUID
            - created_at UTC
            - apply_order (delete blocks deep->shallow if depths available)
            - default modified_time preconditions (v1)
        """
        ops_copy: list[PlanOperation] = copy.deepcopy(self._ops)

        # Attach modified_time preconditions (in-place on copied ops).
        apply_default_preconditions(ops_copy, self._snapshot.files_by_local_id)

        depth_map = self._compute_depths()
        apply_order = build_apply_order(ops_copy, depth_by_local_id=depth_map)

        return SyncPlan(
            plan_id=new_plan_id(),
            remote_root_id=self.root_local_id,
            created_at=now_utc(),
            operations=sorted(ops_copy, key=lambda o: o.seq),
            apply_order=apply_order,
        )

    # ----------------------------
    # Internals
    # ----------------------------
    def _next_seq(self) -> int:
        return len(self._ops)

    def _compute_depths(self) -> dict[str, int]:
        """
        Compute shortest depth (root -> node) within current snapshot.

        Spec decision:
            Depth is the minimum distance from root (BFS).
        """
        if not self._snapshot.has(self.root_local_id):
            return {}

        depth: dict[str, int] = {self.root_local_id: 0}
        q: deque[str] = deque([self.root_local_id])

        while q:
            cur = q.popleft()
            cur_depth = depth[cur]
            for child_id in self._snapshot.children_by_parent_local_id.get(cur, set()):
                if child_id not in self._snapshot.files_by_local_id:
                    continue
                if child_id not in depth:
                    depth[child_id] = cur_depth + 1
                    q.append(child_id)

        return depth
