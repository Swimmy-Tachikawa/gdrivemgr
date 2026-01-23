import unittest
from datetime import datetime, timezone

from gdrivemgr.models import FileInfo


class TestFileInfo(unittest.TestCase):
    def test_file_info_required_fields(self) -> None:
        info = FileInfo(
            local_id="L1",
            name="n",
            mime_type="text/plain",
            parents=["P1"],
        )
        self.assertEqual(info.local_id, "L1")
        self.assertIsNone(info.file_id)
        self.assertFalse(info.trashed)
        self.assertIsNone(info.modified_time)
        self.assertIsNone(info.created_time)

    def test_file_info_optional_fields(self) -> None:
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        info = FileInfo(
            local_id="F1",
            file_id="F1",
            name="doc",
            mime_type="application/pdf",
            parents=["P1"],
            trashed=True,
            modified_time=dt,
            created_time=dt,
            size=123,
            md5_checksum="abc",
        )
        self.assertEqual(info.file_id, "F1")
        self.assertTrue(info.trashed)
        self.assertEqual(info.modified_time, dt)
        self.assertEqual(info.size, 123)
        self.assertEqual(info.md5_checksum, "abc")


if __name__ == "__main__":
    unittest.main()
