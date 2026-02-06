"""Strict validation helpers for GoogleDriveLocal."""

from __future__ import annotations

from collections import deque

from gdrivemgr.errors import LocalValidationError
from gdrivemgr.util.mime import is_folder

from .snapshot import DriveSnapshot


def validate_exists(snapshot: DriveSnapshot, local_id: str, what: str) -> None:
    if not snapshot.has(local_id):
        raise LocalValidationError(f"{what} does not exist: {local_id}")


def validate_is_folder(snapshot: DriveSnapshot, local_id: str, what: str) -> None:
    info = snapshot.get(local_id)
    if not is_folder(info.mime_type):
        raise LocalValidationError(f"{what} must be a folder: {local_id}")


def validate_not_root(root_local_id: str, target_local_id: str, action: str) -> None:
    if target_local_id == root_local_id:
        raise LocalValidationError(f"Root is protected: cannot {action} root")


def validate_not_tombstoned(
    tombstoned: set[str],
    target_local_id: str,
    what: str,
) -> None:
    if target_local_id in tombstoned:
        raise LocalValidationError(f"{what} is already scheduled for deletion: "
                                   f"{target_local_id}")


def validate_move_single_parent(snapshot: DriveSnapshot, target_local_id: str) -> None:
    info = snapshot.get(target_local_id)
    if len(info.parents) >= 2:
        raise LocalValidationError(
            "MOVE is not allowed for multi-parent items in v1: "
            f"{target_local_id}"
        )


def validate_move_no_cycle(
    snapshot: DriveSnapshot,
    target_local_id: str,
    new_parent_local_id: str,
) -> None:
    """
    Reject cycles: if target appears on the ancestor chain of new_parent.

    Spec decision:
        Walk from new_parent towards root (following parents); if target is hit,
        the move is cyclic and must be rejected.
    """
    if target_local_id == new_parent_local_id:
        raise LocalValidationError("MOVE would create a cycle (target == new_parent)")

    q: deque[str] = deque([new_parent_local_id])
    visited: set[str] = set()

    while q:
        cur = q.popleft()
        if cur in visited:
            continue
        visited.add(cur)

        if cur == target_local_id:
            raise LocalValidationError("MOVE would create a cycle")

        if not snapshot.has(cur):
            # Parent outside of scope; stop climbing this branch.
            continue

        cur_info = snapshot.get(cur)
        for parent in cur_info.parents:
            if parent not in visited:
                q.append(parent)
