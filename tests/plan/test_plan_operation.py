import unittest

from gdrivemgr.plan import Action, PlanOperation


class TestPlanOperation(unittest.TestCase):
    def test_validate_required_fields_create_folder(self) -> None:
        op = PlanOperation(
            op_id="o1",
            seq=0,
            action=Action.CREATE_FOLDER,
            parent_local_id="p1",
            name="n",
            result_local_id="r1",
        )
        op.validate_required_fields()

    def test_validate_required_fields_missing(self) -> None:
        op = PlanOperation(op_id="o1", seq=0, action=Action.MOVE, target_local_id="t")
        with self.assertRaises(ValueError):
            op.validate_required_fields()


if __name__ == "__main__":
    unittest.main()
