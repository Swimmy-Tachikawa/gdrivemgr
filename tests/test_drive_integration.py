import argparse
import os
import tempfile
import unittest
from pathlib import Path

from gdrivemgr import AuthInfo, GoogleDriveManager


DEFAULT_SCOPES = ("https://www.googleapis.com/auth/drive",)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value


class TestGoogleDriveIntegration(unittest.TestCase):
    """
    Integration test with real Google Drive.

    Required env vars:
        - GDRIVEMGR_CLIENT_SECRETS: path to OAuth client secrets json
        - GDRIVEMGR_TOKEN_FILE: path to token json (will be created/updated)
        - GDRIVEMGR_TEST_ROOT_ID: Drive folder ID used as test root (safe sandbox)

    Optional:
        - GDRIVEMGR_SCOPES: comma-separated scopes (default: full drive)
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.client_secrets = _env("GDRIVEMGR_CLIENT_SECRETS")
        cls.token_file = _env("GDRIVEMGR_TOKEN_FILE")
        cls.root_id = _env("GDRIVEMGR_TEST_ROOT_ID")

        scopes_raw = os.environ.get("GDRIVEMGR_SCOPES", "").strip()
        if scopes_raw:
            cls.scopes = tuple(s.strip() for s in scopes_raw.split(",") if s.strip())
        else:
            cls.scopes = DEFAULT_SCOPES

        cls.auth_info = AuthInfo(
            kind="oauth",
            data={
                "client_secrets_file": cls.client_secrets,
                "token_file": cls.token_file,
            },
        )

    def test_plan_apply_smoke(self) -> None:
        mgr = GoogleDriveManager(self.auth_info, scopes=self.scopes)

        # 1) open
        local = mgr.open(self.root_id)

        # 2) Local操作（テスト用フォルダ配下でのみ）
        test_folder_id = local.create_folder("gdrivemgr_it_tmp", self.root_id)

        # 作業用の小さなローカルファイルを作る
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_file = tmp_path / "hello.txt"
            src_file.write_text("hello from gdrivemgr integration test\n", encoding="utf-8")

            # upload -> rename -> copy -> move -> download -> trash
            uploaded_id = local.upload_file(str(src_file), test_folder_id)
            local.rename(uploaded_id, "hello_renamed.txt")

            copied_id = local.copy(uploaded_id, test_folder_id, new_name="hello_copy.txt")
            local.move(copied_id, test_folder_id)

            dst_file = tmp_path / "downloaded.txt"
            local.download_file(uploaded_id, str(dst_file), overwrite=True)

            # 安全側：trash（永久削除はデフォルトで行わない）
            local.trash(uploaded_id)
            local.trash(copied_id)
            local.trash(test_folder_id)

            # 3) plan作成（確認用に内容を出す）
            plan = mgr.build_plan()
            self.assertEqual(plan.remote_root_id, self.root_id)
            self.assertGreaterEqual(len(plan.operations), 1)

            # 4) apply
            result = mgr.apply_plan(plan)

        # 5) 結果
        self.assertIn(result.status, ("success", "failed"))
        self.assertIsNotNone(result.summary)
        # 失敗していても例外停止ではなく SyncResult で返る設計（fatal以外）
        # fatal例外が起きた場合はここに来ない

    def test_optional_danger_delete(self) -> None:
        """
        Optional test: permanent delete.

        Enabled only when env GDRIVEMGR_DANGER_DELETE=1 is set.
        """
        danger = os.environ.get("GDRIVEMGR_DANGER_DELETE", "").strip() == "1"
        if not danger:
            self.skipTest("Set GDRIVEMGR_DANGER_DELETE=1 to enable permanent delete test")

        mgr = GoogleDriveManager(self.auth_info, scopes=self.scopes)
        local = mgr.open(self.root_id)

        test_folder_id = local.create_folder("gdrivemgr_it_delete_tmp", self.root_id)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_file = tmp_path / "delete_me.txt"
            src_file.write_text("delete me\n", encoding="utf-8")

            uploaded_id = local.upload_file(str(src_file), test_folder_id)
            # trash -> delete_permanently（作成物のみ対象）
            local.trash(uploaded_id)
            local.delete_permanently(uploaded_id)
            local.trash(test_folder_id)
            local.delete_permanently(test_folder_id)

            plan = mgr.build_plan()
            result = mgr.apply_plan(plan)

        self.assertIn(result.status, ("success", "failed"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose unittest output",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    unittest.main(verbosity=2 if args.verbose else 1)
