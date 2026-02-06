import unittest

from gdrivemgr.auth import AuthInfo


class TestAuthInfo(unittest.TestCase):
    def test_auth_info_valid_oauth(self) -> None:
        info = AuthInfo(
            kind="oauth",
            data={
                "client_secrets_file": "/tmp/client_secrets.json",
                "token_file": "/tmp/token.json",
            },
        )
        self.assertEqual(info.kind, "oauth")
        self.assertIn("client_secrets_file", info.data)

    def test_auth_info_invalid_kind(self) -> None:
        with self.assertRaises(ValueError):
            AuthInfo(kind="service_account", data={})

    def test_auth_info_missing_keys(self) -> None:
        with self.assertRaises(ValueError):
            AuthInfo(kind="oauth", data={"client_secrets_file": "x"})


if __name__ == "__main__":
    unittest.main()
