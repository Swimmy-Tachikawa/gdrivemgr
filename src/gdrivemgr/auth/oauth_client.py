"""OAuth client utilities for gdrivemgr."""

from __future__ import annotations

import os
from typing import Sequence

from gdrivemgr.errors import AuthError, InvalidArgumentError

from .auth_info import AuthInfo


class OAuthClient:
    """Create and manage OAuth credentials and Drive API service objects."""

    def __init__(self, auth_info: AuthInfo) -> None:
        if auth_info.kind != "oauth":
            raise InvalidArgumentError("OAuthClient requires AuthInfo(kind='oauth')")
        self._auth_info = auth_info

    def get_credentials(self, scopes: Sequence[str], ensure_valid: bool = True):
        """
        Return OAuth credentials for the given scopes.

        Args:
            scopes: OAuth scopes.
            ensure_valid: If True, refresh credentials when possible.

        Returns:
            google.oauth2.credentials.Credentials

        Raises:
            AuthError: on load/refresh/flow failures.
            InvalidArgumentError: if scopes is invalid.
        """
        if not scopes or not all(isinstance(s, str) and s.strip() for s in scopes):
            raise InvalidArgumentError("scopes must be a non-empty sequence of strings")

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except Exception as exc:  # pragma: no cover
            raise AuthError(
                "Google auth libraries are not available",
                details={"hint": "Install google-auth and google-auth-oauthlib"},
                cause=exc,
            ) from exc

        token_file = self._auth_info.token_file
        creds = None

        if os.path.exists(token_file):
            try:
                creds = Credentials.from_authorized_user_file(
                    token_file,
                    scopes=list(scopes),
                )
            except Exception as exc:
                raise AuthError(
                    "Failed to load token_file",
                    details={"token_file": token_file},
                    cause=exc,
                ) from exc

            # IMPORTANT:
            # When ensure_valid is False, return loaded credentials as-is.
            if not ensure_valid:
                return creds

            # ensure_valid=True: refresh if possible.
            if not creds.valid and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self._save_credentials(creds)
                except Exception as exc:
                    raise AuthError(
                        "Failed to refresh OAuth credentials",
                        details={"token_file": token_file},
                        cause=exc,
                    ) from exc

            if creds.valid:
                return creds

        # No token, or token could not be validated/refreshed -> run OAuth flow.
        client_secrets = self._auth_info.client_secrets_file
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets,
                scopes=list(scopes),
            )
            creds = flow.run_local_server(port=0)
            self._save_credentials(creds)
            return creds
        except Exception as exc:
            raise AuthError(
                "OAuth authorization flow failed",
                details={
                    "client_secrets_file": client_secrets,
                    "token_file": token_file,
                },
                cause=exc,
            ) from exc

    def build_drive_service(self, scopes: Sequence[str], ensure_valid: bool = True):
        """
        Build a Drive API service resource.

        Returns:
            googleapiclient.discovery.Resource
        """
        try:
            from googleapiclient.discovery import build
        except Exception as exc:  # pragma: no cover
            raise AuthError(
                "google-api-python-client is not available",
                details={"hint": "Install google-api-python-client"},
                cause=exc,
            ) from exc

        creds = self.get_credentials(scopes=scopes, ensure_valid=ensure_valid)
        try:
            return build("drive", "v3", credentials=creds, cache_discovery=False)
        except Exception as exc:
            raise AuthError("Failed to build Drive service", cause=exc) from exc

    def _save_credentials(self, creds) -> None:
        token_file = self._auth_info.token_file
        token_dir = os.path.dirname(token_file)
        if token_dir:
            os.makedirs(token_dir, exist_ok=True)

        try:
            with open(token_file, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except Exception as exc:
            raise AuthError(
                "Failed to save OAuth token file",
                details={"token_file": token_file},
                cause=exc,
            ) from exc
