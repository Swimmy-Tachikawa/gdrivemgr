import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from gdrivemgr.controller.drive_controller import (
    GoogleDriveController,
    _file_dict_to_file_info,
)
from gdrivemgr.errors import NotFoundError, RateLimitError
from gdrivemgr.util.time import to_rfc3339


class TestDriveControllerHelpers(unittest.TestCase):
    def test_file_dict_to_file_info_parses_times(self) -> None:
        dt = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        data = {
            "id": "F1",
            "name": "n",
            "mimeType": "text/plain",
            "parents": ["P1"],
            "trashed": False,
            "modifiedTime": to_rfc3339(dt),
            "createdTime": to_rfc3339(dt),
            "size": "123",
            "md5Checksum": "abc",
        }
        info = _file_dict_to_file_info(data)
        self.assertEqual(info.local_id, "F1")
        self.assertEqual(info.file_id, "F1")
        self.assertEqual(info.size, 123)
        self.assertEqual(info.md5_checksum, "abc")
        self.assertEqual(info.modified_time, dt)
        self.assertEqual(info.created_time, dt)


class TestDriveControllerMocked(unittest.TestCase):
    def _mock_service_with_list(self, files_payload, next_token=None):
        service = Mock()
        files_resource = Mock()
        request = Mock()

        service.files.return_value = files_resource
        request.execute.return_value = {
            "files": files_payload,
            "nextPageToken": next_token,
        }
        files_resource.list.return_value = request
        return service, files_resource, request

    def test_list_children_includes_supports_all_drives_kwargs(self) -> None:
        service, files_resource, _ = self._mock_service_with_list([])
        controller = GoogleDriveController.from_service(service, supports_all_drives=True)

        controller.list_children("P1")

        kwargs = files_resource.list.call_args.kwargs
        self.assertTrue(kwargs.get("supportsAllDrives"))
        self.assertTrue(kwargs.get("includeItemsFromAllDrives"))
        self.assertIn("'P1' in parents", kwargs["q"])

    def test_get_maps_http_404_to_not_found(self) -> None:
        from googleapiclient.errors import HttpError

        service = Mock()
        files_resource = Mock()
        req = Mock()

        service.files.return_value = files_resource
        files_resource.get.return_value = req

        resp = Mock()
        resp.status = 404
        resp.reason = "Not Found"
        req.execute.side_effect = HttpError(resp=resp, content=b"{}")

        controller = GoogleDriveController.from_service(service)

        with self.assertRaises(NotFoundError):
            controller.get("X")

    def test_retry_on_429(self) -> None:
        from googleapiclient.errors import HttpError

        service = Mock()
        files_resource = Mock()
        req = Mock()

        service.files.return_value = files_resource
        files_resource.get.return_value = req

        resp = Mock()
        resp.status = 429
        resp.reason = "rateLimitExceeded"
        err_body = {
            "error": {
                "message": "rate limited",
                "errors": [{"reason": "rateLimitExceeded"}],
            }
        }
        http_err = HttpError(resp=resp, content=json.dumps(err_body).encode("utf-8"))

        # Fail twice, then succeed.
        req.execute.side_effect = [
            http_err,
            http_err,
            {"id": "F1", "name": "n", "mimeType": "text/plain", "parents": []},
        ]

        controller = GoogleDriveController.from_service(service)

        with patch("time.sleep", return_value=None) as _:
            info = controller.get("F1")

        self.assertEqual(info.file_id, "F1")
        self.assertEqual(req.execute.call_count, 3)

    def test_map_429_to_rate_limit_error(self) -> None:
        from googleapiclient.errors import HttpError

        service = Mock()
        files_resource = Mock()
        req = Mock()

        service.files.return_value = files_resource
        files_resource.get.return_value = req

        resp = Mock()
        resp.status = 429
        resp.reason = "rateLimitExceeded"
        err_body = {
            "error": {
                "message": "rate limited",
                "errors": [{"reason": "rateLimitExceeded"}],
            }
        }
        http_err = HttpError(resp=resp, content=json.dumps(err_body).encode("utf-8"))
        req.execute.side_effect = http_err

        controller = GoogleDriveController.from_service(service)

        with patch("time.sleep", return_value=None):
            with self.assertRaises(RateLimitError):
                controller.get("X")


if __name__ == "__main__":
    unittest.main()
