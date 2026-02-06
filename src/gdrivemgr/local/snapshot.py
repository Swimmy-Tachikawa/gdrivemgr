"""Local snapshot and indexes for GoogleDriveLocal."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import DefaultDict

from gdrivemgr.models import FileInfo


@dataclass(slots=True)
class DriveSnapshot:
    """
    In-memory representation of Drive state within the managed root scope.

    Indexes (required by spec):
        - files_by_local_id
        - children_by_parent_local_id
        - name_index_by_parent_local_id
    """

    files_by_local_id: dict[str, FileInfo] = field(default_factory=dict)
    children_by_parent_local_id: dict[str, set[str]] = field(default_factory=dict)
    name_index_by_parent_local_id: dict[str, dict[str, list[str]]] = field(
        default_factory=dict
    )

    @classmethod
    def from_file_infos(cls, files: list[FileInfo]) -> DriveSnapshot:
        """
        Build snapshot from a list of FileInfo.

        Notes:
            - parents are expected to be local_ids within the same scope (for
              existing Drive items, local_id == file_id).
        """
        snap = cls()
        for info in files:
            snap._insert_file(info)
        return snap

    def clone(self) -> DriveSnapshot:
        """Deep-clone this snapshot (including indexes)."""
        # Clone FileInfo objects (to avoid mutating the base snapshot).
        new_files: dict[str, FileInfo] = {}
        for local_id, info in self.files_by_local_id.items():
            new_files[local_id] = FileInfo(
                local_id=info.local_id,
                file_id=info.file_id,
                name=info.name,
                mime_type=info.mime_type,
                parents=list(info.parents),
                trashed=info.trashed,
                modified_time=info.modified_time,
                created_time=info.created_time,
                size=info.size,
                md5_checksum=info.md5_checksum,
            )

        new_children: dict[str, set[str]] = {
            parent: set(children) for parent, children in self.children_by_parent_local_id.items()
        }

        new_name_index: dict[str, dict[str, list[str]]] = {}
        for parent, name_map in self.name_index_by_parent_local_id.items():
            new_name_index[parent] = {name: list(ids) for name, ids in name_map.items()}

        return DriveSnapshot(
            files_by_local_id=new_files,
            children_by_parent_local_id=new_children,
            name_index_by_parent_local_id=new_name_index,
        )

    # ----------------------------
    # Query helpers
    # ----------------------------
    def has(self, local_id: str) -> bool:
        return local_id in self.files_by_local_id

    def get(self, local_id: str) -> FileInfo:
        return self.files_by_local_id[local_id]

    def list_children_ids(self, parent_local_id: str) -> list[str]:
        return list(self.children_by_parent_local_id.get(parent_local_id, set()))

    # ----------------------------
    # Mutation helpers (keep indexes consistent)
    # ----------------------------
    def add_file(self, info: FileInfo) -> None:
        """Add a new file and update indexes."""
        self._insert_file(info)

    def remove_file(self, local_id: str) -> None:
        """Remove file from snapshot and indexes."""
        info = self.files_by_local_id.get(local_id)
        if not info:
            return

        self._detach_from_parents(info)
        self.files_by_local_id.pop(local_id, None)

        # Remove children index entry (children become unreachable but remain).
        self.children_by_parent_local_id.pop(local_id, None)
        self.name_index_by_parent_local_id.pop(local_id, None)

    def rename(self, local_id: str, new_name: str) -> None:
        """Rename a file and update name indexes."""
        info = self.files_by_local_id[local_id]
        old_name = info.name
        if old_name == new_name:
            return

        # Update name index for each parent.
        for parent in info.parents:
            self._remove_name_index(parent, old_name, local_id)
            self._add_name_index(parent, new_name, local_id)

        info.name = new_name

    def replace_parent(self, local_id: str, new_parent_local_id: str) -> None:
        """
        Replace parents with [new_parent_local_id] and update indexes.

        Note:
            Multiple-parents behavior is handled by validators. This method
            implements the move semantics (parent replacement) only.
        """
        info = self.files_by_local_id[local_id]
        old_parents = list(info.parents)

        for parent in old_parents:
            self._remove_child_index(parent, info.name, local_id)

        info.parents = [new_parent_local_id]
        self._add_child_index(new_parent_local_id, info.name, local_id)

    # ----------------------------
    # Internal index maintenance
    # ----------------------------
    def _insert_file(self, info: FileInfo) -> None:
        self.files_by_local_id[info.local_id] = info

        # Ensure empty containers exist.
        self.children_by_parent_local_id.setdefault(info.local_id, set())
        self.name_index_by_parent_local_id.setdefault(info.local_id, {})

        for parent in info.parents:
            self._add_child_index(parent, info.name, info.local_id)

    def _detach_from_parents(self, info: FileInfo) -> None:
        for parent in info.parents:
            self._remove_child_index(parent, info.name, info.local_id)

    def _add_child_index(self, parent: str, name: str, child: str) -> None:
        self.children_by_parent_local_id.setdefault(parent, set()).add(child)
        self._add_name_index(parent, name, child)

    def _remove_child_index(self, parent: str, name: str, child: str) -> None:
        if parent in self.children_by_parent_local_id:
            self.children_by_parent_local_id[parent].discard(child)
        self._remove_name_index(parent, name, child)

    def _add_name_index(self, parent: str, name: str, child: str) -> None:
        parent_map = self.name_index_by_parent_local_id.setdefault(parent, {})
        ids = parent_map.setdefault(name, [])
        if child not in ids:
            ids.append(child)

    def _remove_name_index(self, parent: str, name: str, child: str) -> None:
        parent_map = self.name_index_by_parent_local_id.get(parent)
        if not parent_map:
            return
        ids = parent_map.get(name)
        if not ids:
            return
        if child in ids:
            ids.remove(child)
        if not ids:
            parent_map.pop(name, None)
