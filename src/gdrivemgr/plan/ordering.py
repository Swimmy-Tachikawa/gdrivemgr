"""Apply ordering rules for SyncPlan operations."""

from __future__ import annotations

from typing import Optional

from .actions import Action
from .operation import PlanOperation


_DELETE_ACTIONS: set[Action] = {Action.TRASH, Action.DELETE_PERMANENT}


def build_apply_order(
    operations: list[PlanOperation],
    depth_by_local_id: Optional[dict[str, int]] = None,
) -> list[str]:
    """
    Build apply_order from operations.

    Rules:
        - Base order: seq ascending.
        - For contiguous blocks of delete actions (TRASH/DELETE_PERMANENT),
          reorder within the block by depth (deep -> shallow) if depth is known
          for all delete targets in the block. Otherwise keep seq order.
    """
    ops = sorted(operations, key=lambda op: op.seq)
    reordered: list[PlanOperation] = []

    i = 0
    while i < len(ops):
        op = ops[i]
        if op.action not in _DELETE_ACTIONS:
            reordered.append(op)
            i += 1
            continue

        j = i
        while j < len(ops) and ops[j].action in _DELETE_ACTIONS:
            j += 1

        block = ops[i:j]
        reordered.extend(_reorder_delete_block(block, depth_by_local_id))
        i = j

    return [op.op_id for op in reordered]


def _reorder_delete_block(
    block: list[PlanOperation],
    depth_by_local_id: Optional[dict[str, int]],
) -> list[PlanOperation]:
    if not depth_by_local_id:
        return block

    depths: list[int] = []
    for op in block:
        target = op.target_local_id
        if not target:
            return block
        if target not in depth_by_local_id:
            return block
        depths.append(depth_by_local_id[target])

    # Sort deep -> shallow, tie-breaker: seq ascending.
    return sorted(
        block,
        key=lambda op: (-depth_by_local_id[op.target_local_id], op.seq),  # type: ignore[index]
    )
