import unittest

import gdrivemgr


class TestPublicApi(unittest.TestCase):
    def test_top_level_exports_exist(self) -> None:
        self.assertTrue(hasattr(gdrivemgr, "GoogleDriveManager"))
        self.assertTrue(hasattr(gdrivemgr, "GoogleDriveLocal"))
        self.assertTrue(hasattr(gdrivemgr, "AuthInfo"))
        self.assertTrue(hasattr(gdrivemgr, "OAuthClient"))

        self.assertTrue(hasattr(gdrivemgr, "Action"))
        self.assertTrue(hasattr(gdrivemgr, "SyncPlan"))
        self.assertTrue(hasattr(gdrivemgr, "FileInfo"))
        self.assertTrue(hasattr(gdrivemgr, "SyncResult"))

        self.assertTrue(hasattr(gdrivemgr, "GDriveMgrError"))
        self.assertTrue(hasattr(gdrivemgr, "InvalidStateError"))

    def test___all___is_defined(self) -> None:
        self.assertTrue(hasattr(gdrivemgr, "__all__"))
        self.assertIn("GoogleDriveManager", gdrivemgr.__all__)
        self.assertIn("GDriveMgrError", gdrivemgr.__all__)


if __name__ == "__main__":
    unittest.main()
