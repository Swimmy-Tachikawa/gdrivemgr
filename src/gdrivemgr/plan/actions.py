"""Plan actions for gdrivemgr."""

from __future__ import annotations

from enum import Enum


class Action(str, Enum):
    """Supported plan actions (v1)."""

    CREATE_FOLDER = "CREATE_FOLDER"
    COPY = "COPY"
    RENAME = "RENAME"
    MOVE = "MOVE"
    TRASH = "TRASH"
    DELETE_PERMANENT = "DELETE_PERMANENT"
    UPLOAD_FILE = "UPLOAD_FILE"
    DOWNLOAD_FILE = "DOWNLOAD_FILE"
