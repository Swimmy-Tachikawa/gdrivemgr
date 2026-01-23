import unittest

from gdrivemgr.util.mime import (
    FOLDER_MIME,
    is_folder,
    is_google_app,
    is_google_docs_download_disallowed,
)


class TestUtilMime(unittest.TestCase):
    def test_is_folder(self) -> None:
        self.assertTrue(is_folder(FOLDER_MIME))
        self.assertFalse(is_folder("text/plain"))

    def test_is_google_app(self) -> None:
        self.assertTrue(is_google_app("application/vnd.google-apps.document"))
        self.assertTrue(is_google_app("application/vnd.google-apps.spreadsheet"))
        self.assertTrue(is_google_app("application/vnd.google-apps.presentation"))

        # Prefix-based detection for unlisted Google apps types.
        self.assertTrue(is_google_app("application/vnd.google-apps.some-new-type"))

        self.assertFalse(is_google_app("application/pdf"))

    def test_is_google_docs_download_disallowed(self) -> None:
        self.assertTrue(is_google_docs_download_disallowed(FOLDER_MIME))
        self.assertTrue(
            is_google_docs_download_disallowed("application/vnd.google-apps.document")
        )
        self.assertTrue(
            is_google_docs_download_disallowed(
                "application/vnd.google-apps.some-new-type"
            )
        )
        self.assertFalse(is_google_docs_download_disallowed("text/plain"))
        self.assertFalse(is_google_docs_download_disallowed("application/pdf"))
