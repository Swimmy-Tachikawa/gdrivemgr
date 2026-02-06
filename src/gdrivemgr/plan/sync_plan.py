"""SyncPlan model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .operation import PlanOperation


@dataclass(slots=True)
class SyncPlan:
    """A plan that can be reviewed and then applied safely."""

    plan_id: str
    remote_root_id: str
    created_at: datetime
    operations: list[PlanOperation]
    apply_order: list[str]
