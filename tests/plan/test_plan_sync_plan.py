import unittest
from datetime import datetime, timezone

from gdrivemgr.plan import Action, PlanOperation, SyncPlan


class TestSyncPlan(unittest.TestCase):
    def test_sync_plan_fields(self) -> None:
        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        ops = [PlanOperation(op_id="o1", seq=0, action=Action.MOVE)]
        plan = SyncPlan(
            plan_id="p1",
            remote_root_id="root",
            created_at=created_at,
            operations=ops,
            apply_order=["o1"],
        )
        self.assertEqual(plan.remote_root_id, "root")
        self.assertEqual(plan.apply_order, ["o1"])


if __name__ == "__main__":
    unittest.main()
