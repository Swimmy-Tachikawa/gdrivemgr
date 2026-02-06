"""Authentication information for gdrivemgr (OAuth only, v1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class AuthInfo:
    """
    Authentication information.

    v1 supports OAuth only:
        kind = "oauth"
        data must include:
            - client_secrets_file
            - token_file
    """

    kind: str
    data: dict[str, Any]

    def __post_init__(self) -> None:
        if self.kind != "oauth":
            raise ValueError("AuthInfo.kind must be 'oauth' in v1")

        if not isinstance(self.data, dict):
            raise TypeError("AuthInfo.data must be a dict")

        for key in ("client_secrets_file", "token_file"):
            value = self.data.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"AuthInfo.data['{key}'] must be a non-empty string")

    @property
    def client_secrets_file(self) -> str:
        """Path to OAuth client secrets JSON."""
        return str(self.data["client_secrets_file"])

    @property
    def token_file(self) -> str:
        """Path to OAuth token JSON (authorized user)."""
        return str(self.data["token_file"])
