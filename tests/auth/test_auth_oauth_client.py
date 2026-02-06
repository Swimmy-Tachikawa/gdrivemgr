import json
import tempfile
import unittest
from pathlib import Path

from gdrivemgr.auth import AuthInfo, OAuthClient


class TestOAuthClient(unittest.TestCase):
    def test_get_credentials_loads_token_file_without_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            token_file = tmp_path / "token.json"

            token_payload = {
                "token": "fake-token",
                "refresh_token": "fake-refresh-token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "fake-client-id",
                "client_secret": "fake-client-secret",
                "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
                "type": "authorized_user",
            }
            token_file.write_text(json.dumps(token_payload), encoding="utf-8")

            info = AuthInfo(
                kind="oauth",
                data={
                    "client_secrets_file": str(tmp_path / "client_secrets.json"),
                    "token_file": str(token_file),
                },
            )
            client = OAuthClient(info)
            creds = client.get_credentials(
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
                ensure_valid=False,
            )

            # Credentials object should be created and have a refresh_token.
            self.assertTrue(hasattr(creds, "refresh_token"))
            self.assertEqual(creds.refresh_token, "fake-refresh-token")


if __name__ == "__main__":
    unittest.main()
