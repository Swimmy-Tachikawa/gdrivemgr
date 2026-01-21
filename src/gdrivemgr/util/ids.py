from __future__ import annotations

import uuid


def new_uuid() -> str:
    """Generate a UUID4 string."""
    return str(uuid.uuid4())


def new_plan_id() -> str:
    """Generate a new SyncPlan ID."""
    return new_uuid()


def new_op_id() -> str:
    """Generate a new PlanOperation ID."""
    return new_uuid()


def new_local_id() -> str:
    """Generate a new local_id for items that don't have a Drive file_id yet."""
    return new_uuid()
