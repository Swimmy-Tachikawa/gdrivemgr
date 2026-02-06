import unittest
from datetime import datetime, timezone

from gdrivemgr.errors import ConflictError
from gdrivemgr.models import FileInfo
from gdrivemgr.plan import (
    Action,
    PlanOperation,
    apply_default_preconditions,
    check_modified_time_precondition,
)


class TestPreconditions(unittest.TestCase):
    def test_apply_default_preconditions_sets_expected_modified_time(self) -> None:
        dt = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        files = {
            "t1": FileInfo(
                local_id="t1",
                file_id="t1",
                name="x",
                mime_type="text/plain",
                parents=["root"],
                modified_time=dt,
            )
        }
        ops = [
            PlanOperation(op_id="o1", seq=0, action=Action.RENAME, target_local_id="t1")
        ]
        apply_default_preconditions(ops, files)
        self.assertIsNotNone(ops[0].precondition)
        self.assertIn("expected_modified_time", ops[0].precondition)

    def test_check_modified_time_precondition(self) -> None:
        expected = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        pre = {"expected_modified_time": expected}

        check_modified_time_precondition(pre, expected)

        different = datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
        with self.assertRaises(ConflictError):
            check_modified_time_precondition(pre, different)


if __name__ == "__main__":
    unittest.main()
