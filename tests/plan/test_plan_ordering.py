import unittest

from gdrivemgr.plan import Action, PlanOperation, build_apply_order


class TestOrdering(unittest.TestCase):
    def test_build_apply_order_seq_default(self) -> None:
        ops = [
            PlanOperation(op_id="a", seq=2, action=Action.MOVE),
            PlanOperation(op_id="b", seq=1, action=Action.RENAME),
            PlanOperation(op_id="c", seq=0, action=Action.TRASH, target_local_id="x"),
        ]
        order = build_apply_order(ops)
        self.assertEqual(order, ["c", "b", "a"])

    def test_delete_block_reordered_by_depth(self) -> None:
        ops = [
            PlanOperation(
                op_id="d1",
                seq=0,
                action=Action.TRASH,
                target_local_id="parent",
            ),
            PlanOperation(
                op_id="d2",
                seq=1,
                action=Action.DELETE_PERMANENT,
                target_local_id="child",
            ),
        ]
        depth = {"parent": 1, "child": 2}
        order = build_apply_order(ops, depth_by_local_id=depth)
        self.assertEqual(order, ["d2", "d1"])

    def test_delete_block_not_reordered_if_missing_depth(self) -> None:
        ops = [
            PlanOperation(op_id="d1", seq=0, action=Action.TRASH, target_local_id="p"),
            PlanOperation(
                op_id="d2",
                seq=1,
                action=Action.DELETE_PERMANENT,
                target_local_id="c",
            ),
        ]
        depth = {"p": 1}
        order = build_apply_order(ops, depth_by_local_id=depth)
        self.assertEqual(order, ["d1", "d2"])

    def test_reorder_only_within_contiguous_delete_block(self) -> None:
        ops = [
            PlanOperation(op_id="d1", seq=0, action=Action.TRASH, target_local_id="p"),
            PlanOperation(op_id="x1", seq=1, action=Action.RENAME, target_local_id="t"),
            PlanOperation(
                op_id="d2",
                seq=2,
                action=Action.DELETE_PERMANENT,
                target_local_id="c",
            ),
        ]
        depth = {"p": 1, "c": 2}
        order = build_apply_order(ops, depth_by_local_id=depth)
        # Not contiguous, so no swap occurs.
        self.assertEqual(order, ["d1", "x1", "d2"])


if __name__ == "__main__":
    unittest.main()
