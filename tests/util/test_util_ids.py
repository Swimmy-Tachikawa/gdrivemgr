import unittest
import uuid

from gdrivemgr.util.ids import new_local_id, new_op_id, new_plan_id, new_uuid


class TestUtilIds(unittest.TestCase):
    def test_new_uuid_is_valid_uuid4(self) -> None:
        value = new_uuid()
        parsed = uuid.UUID(value)
        self.assertEqual(str(parsed), value)
        self.assertEqual(parsed.version, 4)

    def test_new_plan_id_is_valid_uuid4(self) -> None:
        value = new_plan_id()
        parsed = uuid.UUID(value)
        self.assertEqual(parsed.version, 4)

    def test_new_op_id_is_valid_uuid4(self) -> None:
        value = new_op_id()
        parsed = uuid.UUID(value)
        self.assertEqual(parsed.version, 4)

    def test_new_local_id_is_valid_uuid4(self) -> None:
        value = new_local_id()
        parsed = uuid.UUID(value)
        self.assertEqual(parsed.version, 4)

    def test_ids_are_unique(self) -> None:
        values = {new_uuid(), new_uuid(), new_uuid()}
        self.assertEqual(len(values), 3)
