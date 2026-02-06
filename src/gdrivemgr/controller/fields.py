"""Field definitions for Google Drive API responses."""

from __future__ import annotations

FILE_FIELDS: str = (
    "id,"
    "name,"
    "mimeType,"
    "parents,"
    "trashed,"
    "modifiedTime,"
    "createdTime,"
    "size,"
    "md5Checksum"
)

LIST_FIELDS: str = f"nextPageToken,files({FILE_FIELDS})"
