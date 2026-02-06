import unittest
from datetime import datetime, timezone

from gdrivemgr.errors import LocalValidationError
from gdrivemgr.local import GoogleDriveLocal
from gdrivemgr.models import FileInfo
from gdrivemgr.plan import Action
from gdrivemgr.util.mime import FOLDER_MIME


class TestGoogleDriveLocal(unittest.TestCase):
    def _make_local(self) -> GoogleDriveLocal:
        root = FileInfo(
            local_id="root",
            file_id="root",
            name="ROOT",
            mime_type=FOLDER_MIME,
            parents=[],
        )
        a = FileInfo(
            local_id="A",
            file_id="A",
            name="A",
            mime_type=FOLDER_MIME,
            parents=["root"],
        )
        b = FileInfo(
            local_id="B",
            file_id="B",
            name="B",
            mime_type=FOLDER_MIME,
            parents=["A"],
        )
        f = FileInfo(
            local_id="F",
            file_id="F",
            name="file.txt",
            mime_type="text/plain",
            parents=["A"],
            modified_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        return GoogleDriveLocal.from_file_infos("root", [root, a, b, f])

    def test_create_folder_and_op(self) -> None:
        local = self._make_local()
        new_id = local.create_folder("X", "root")
        self.assertTrue(local.get(new_id).name, "X")
        ops = local.list_ops()
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].action, Action.CREATE_FOLDER)

    def test_move_requires_existing_parent(self) -> None:
        local = self._make_local()
        with self.assertRaises(LocalValidationError):
            local.move("F", "NOPE")

    def test_root_protection(self) -> None:
        local = self._make_local()
        with self.assertRaises(LocalValidationError):
            local.rename("root", "X")

    def test_cycle_move_rejected(self) -> None:
        local = self._make_local()
        # Attempt to move A under its descendant B
        with self.assertRaises(LocalValidationError):
            local.move("A", "B")

    def test_multi_parent_move_rejected(self) -> None:
        root = FileInfo(
            local_id="root",
            file_id="root",
            name="ROOT",
            mime_type=FOLDER_MIME,
            parents=[],
        )
        other = FileInfo(
            local_id="O",
            file_id="O",
            name="O",
            mime_type=FOLDER_MIME,
            parents=["root"],
        )
        target = FileInfo(
            local_id="X",
            file_id="X",
            name="X",
            mime_type="text/plain",
            parents=["root", "O"],
        )
        local = GoogleDriveLocal.from_file_infos("root", [root, other, target])
        with self.assertRaises(LocalValidationError):
            local.move("X", "O")

    def test_trash_then_rename_rejected(self) -> None:
        local = self._make_local()
        local.trash("F")
        with self.assertRaises(LocalValidationError):
            local.rename("F", "new.txt")

    def test_copy_folder_rejected(self) -> None:
        local = self._make_local()
        with self.assertRaises(LocalValidationError):
            local.copy("A", "root")

    def test_upload_default_name_uses_basename(self) -> None:
        local = self._make_local()
        new_id = local.upload_file("/tmp/hello.txt", "root")
        self.assertEqual(local.get(new_id).name, "hello.txt")

    def test_build_plan_reorders_delete_block_deep_to_shallow(self) -> None:
        local = self._make_local()
        # delete parent A (depth 1), then delete child B (depth 2)
        local.trash("A")
        local.delete_permanently("B")

        plan = local.build_plan()
        # apply_order should put B before A (deep -> shallow) within delete block
        self.assertEqual(plan.apply_order, [plan.operations[1].op_id, plan.operations[0].op_id])

    def test_build_plan_attaches_modified_time_precondition(self) -> None:
        local = self._make_local()
        local.rename("F", "renamed.txt")
        plan = local.build_plan()
        op = plan.operations[0]
        self.assertIsNotNone(op.precondition)
        self.assertIn("expected_modified_time", op.precondition)

    def test_clear_ops_resets_state(self) -> None:
        local = self._make_local()
        local.rename("F", "x.txt")
        self.assertEqual(local.get("F").name, "x.txt")
        local.clear_ops()
        self.assertEqual(local.get("F").name, "file.txt")
        self.assertEqual(len(local.list_ops()), 0)


if __name__ == "__main__":
    unittest.main()
