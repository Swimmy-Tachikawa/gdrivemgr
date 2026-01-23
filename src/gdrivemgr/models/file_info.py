"""Data model for Drive items."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class FileInfo:
    """
    Represents a Drive item tracked by the library.

    Notes:
        - For existing Drive items: local_id == file_id (by spec).
        - For items not created on Drive yet: file_id is None and local_id is a
          generated UUID.
    """

    local_id: str
    name: str
    mime_type: str
    parents: list[str]

    file_id: Optional[str] = None
    trashed: bool = False
    modified_time: Optional[datetime] = None
    created_time: Optional[datetime] = None
    size: Optional[int] = None
    md5_checksum: Optional[str] = None
