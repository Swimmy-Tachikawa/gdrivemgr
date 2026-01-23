import unittest

from gdrivemgr.errors.exceptions import (
    ApiError,
    AuthError,
    ConflictError,
    GDriveMgrError,
    HttpErrorInfo,
    InvalidArgumentError,
    NotFoundError,
    PermissionError,
    QuotaExceededError,
    RateLimitError,
    map_http_error,
)


class TestExceptions(unittest.TestCase):
    def test_base_error_keeps_details_and_cause(self) -> None:
        cause = RuntimeError("root")
        err = GDriveMgrError("msg", details={"k": "v"}, cause=cause)
        self.assertEqual(str(err), "msg")
        self.assertEqual(err.details["k"], "v")
        self.assertIs(err.cause, cause)

    def test_map_http_error_basic(self) -> None:
        err = map_http_error(HttpErrorInfo(status_code=404, message="not found"))
        self.assertIsInstance(err, NotFoundError)

        err = map_http_error(HttpErrorInfo(status_code=400, message="bad req"))
        self.assertIsInstance(err, InvalidArgumentError)

        err = map_http_error(HttpErrorInfo(status_code=429, message="rate"))
        self.assertIsInstance(err, RateLimitError)

        err = map_http_error(HttpErrorInfo(status_code=409, message="conflict"))
        self.assertIsInstance(err, ConflictError)

        err = map_http_error(HttpErrorInfo(status_code=401, message="auth"))
        self.assertIsInstance(err, AuthError)

    def test_map_http_error_403_quota_vs_permission(self) -> None:
        err = map_http_error(
            HttpErrorInfo(status_code=403, reason="quotaExceeded", message="quota")
        )
        self.assertIsInstance(err, QuotaExceededError)

        err = map_http_error(
            HttpErrorInfo(status_code=403, reason="insufficientPermissions", message="x")
        )
        self.assertIsInstance(err, PermissionError)

    def test_map_http_error_5xx_is_api_error(self) -> None:
        err = map_http_error(HttpErrorInfo(status_code=503, message="unavail"))
        self.assertIsInstance(err, ApiError)

    def test_map_http_error_other_is_api_error(self) -> None:
        err = map_http_error(HttpErrorInfo(status_code=418, message="teapot"))
        self.assertIsInstance(err, ApiError)


if __name__ == "__main__":
    unittest.main()
