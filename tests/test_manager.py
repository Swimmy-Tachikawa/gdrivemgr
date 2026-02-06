import unittest
from datetime import datetime, timezone

from gdrivemgr.errors import InvalidStateError, NotFoundError
from gdrivemgr.manager import GoogleDriveManager
from gdrivemgr.models import FileInfo
from gdrivemgr.util.mime import FOLDER_MIME


class FakeController:
    def __init__(self) -> None:
        self.calls = []
        self.dt = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        self.root = FileInfo(
            local_id="root",
            file_id="root",
            name="ROOT",
            mime_type=FOLDER_MIME,
            parents=[],
        )
        self.a = FileInfo(
            local_id="A",
            file_id="A",
            name="A",
            mime_type=FOLDER_MIME,
            parents=["root"],
        )
        self.f = FileInfo(
            local_id="F",
            file_id="F",
            name="file.txt",
            mime_type="text/plain",
            parents=["A"],
            modified_time=self.dt,
        )

    def get(self, file_id: str) -> FileInfo:
        self.calls.append(("get", file_id))
        if file_id == "root":
            return self.root
        if file_id == "F":
            return self.f
        if file_id == "A":
            return self.a
        # created folder ids:
        if file_id == "NF1":
            return FileInfo(
                local_id="NF1",
                file_id="NF1",
                name="NEW",
                mime_type=FOLDER_MIME,
                parents=["root"],
            )
        raise NotFoundError("not found", details={"file_id": file_id})

    def list_tree(self, root_id: str, include_trashed: bool = False):
        self.calls.append(("list_tree", root_id, include_trashed))
        return [self.a, self.f]

    def create_folder(self, name: str, parent_id: str) -> FileInfo:
        self.calls.append(("create_folder", name, parent_id))
        return FileInfo(
            local_id="NF1",
            file_id="NF1",
            name=name,
            mime_type=FOLDER_MIME,
            parents=[parent_id],
        )

    def move(self, file_id: str, new_parent_id: str) -> FileInfo:
        self.calls.append(("move", file_id, new_parent_id))
        return self.get(file_id)

    def rename(self, file_id: str, new_name: str) -> FileInfo:
        self.calls.append(("rename", file_id, new_name))
        return self.get(file_id)

    def copy(self, file_id: str, new_parent_id: str, new_name=None) -> FileInfo:
        self.calls.append(("copy", file_id, new_parent_id, new_name))
        return FileInfo(
            local_id="CP1",
            file_id="CP1",
            name=new_name or "copy",
            mime_type="text/plain",
            parents=[new_parent_id],
        )

    def trash(self, file_id: str) -> None:
        self.calls.append(("trash", file_id))

    def delete_permanently(self, file_id: str) -> None:
        self.calls.append(("delete_permanently", file_id))

    def upload_file(self, local_path: str, parent_id: str, name=None) -> FileInfo:
        self.calls.append(("upload_file", local_path, parent_id, name))
        return FileInfo(
            local_id="UP1",
            file_id="UP1",
            name=name or "up",
            mime_type="application/octet-stream",
            parents=[parent_id],
        )

    def download_file(self, file_id: str, local_path: str, overwrite: bool = False) -> None:
        self.calls.append(("download_file", file_id, local_path, overwrite))


class TestGoogleDriveManager(unittest.TestCase):
    def test_open_build_apply_success(self) -> None:
        controller = FakeController()
        mgr = GoogleDriveManager.from_controller(controller)

        local = mgr.open("root")
        new_folder_local_id = local.create_folder("NEW", "root")
        local.move("F", new_folder_local_id)

        plan = mgr.build_plan()
        result = mgr.apply_plan(plan)

        self.assertEqual(result.status, "success")
        self.assertTrue(result.snapshot_refreshed)
        self.assertIn(new_folder_local_id, result.id_map)
        self.assertEqual(result.id_map[new_folder_local_id], "NF1")

        # Ensure move called with resolved file id and resolved new parent id.
        self.assertIn(("move", "F", "NF1"), controller.calls)

    def test_apply_root_mismatch_is_fatal(self) -> None:
        controller = FakeController()
        mgr = GoogleDriveManager.from_controller(controller)

        mgr.open("root")
        plan = mgr.build_plan()
        plan.remote_root_id = "other"  # type: ignore[misc]

        with self.assertRaises(InvalidStateError):
            mgr.apply_plan(plan)

    def test_apply_nonfatal_error_returns_failed(self) -> None:
        controller = FakeController()
        mgr = GoogleDriveManager.from_controller(controller)

        local = mgr.open("root")
        new_folder_local_id = local.create_folder("NEW", "root")
        local.move("F", new_folder_local_id)

        # Make controller.move fail (non-fatal).
        def bad_move(file_id: str, new_parent_id: str):
            raise NotFoundError("not found")

        controller.move = bad_move  # type: ignore[assignment]

        plan = mgr.build_plan()
        result = mgr.apply_plan(plan)

        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.stopped_op_id)
        self.assertGreaterEqual(result.summary.get("failed", 0), 1)


if __name__ == "__main__":
    unittest.main()
