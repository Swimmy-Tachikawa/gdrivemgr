"""Google Drive API controller (internal use only)."""

from __future__ import annotations

import io
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence, TypeVar

from gdrivemgr.auth import AuthInfo, OAuthClient
from gdrivemgr.errors import (
    ApiError,
    AuthError,
    HttpErrorInfo,
    InvalidArgumentError,
    NetworkError,
    RateLimitError,
    map_http_error,
)
from gdrivemgr.models import FileInfo
from gdrivemgr.util.mime import is_google_docs_download_disallowed
from gdrivemgr.util.time import parse_rfc3339

from .fields import FILE_FIELDS, LIST_FIELDS

T = TypeVar("T")


@dataclass(frozen=True)
class _RetryPolicy:
    max_retries: int = 3
    initial_delay_sec: float = 1.0


class GoogleDriveController:
    """
    Drive API controller (internal only).

    Notes:
        - The Drive `service` object is NOT exposed.
        - `supports_all_drives` is applied to all requests consistently.
    """

    DEFAULT_SCOPES: tuple[str, ...] = ("https://www.googleapis.com/auth/drive",)

    def __init__(
        self,
        auth_info: AuthInfo,
        *,
        scopes: Optional[Sequence[str]] = None,
        supports_all_drives: bool = True,
    ) -> None:
        self._supports_all_drives = supports_all_drives
        self._retry_policy = _RetryPolicy()

        use_scopes = list(scopes) if scopes is not None else list(self.DEFAULT_SCOPES)
        client = OAuthClient(auth_info)
        self._service = client.build_drive_service(use_scopes, ensure_valid=True)

    @classmethod
    def from_service(
        cls,
        service: Any,
        *,
        supports_all_drives: bool = True,
    ) -> "GoogleDriveController":
        """Create controller from a pre-built Drive service (useful for tests)."""
        obj = cls.__new__(cls)
        obj._supports_all_drives = supports_all_drives
        obj._retry_policy = _RetryPolicy()
        obj._service = service
        return obj

    # ----------------------------
    # Public API
    # ----------------------------
    def get(self, file_id: str) -> FileInfo:
        req = self._service.files().get(
            fileId=file_id,
            fields=FILE_FIELDS,
            **self._common_get_kwargs(),
        )
        data = self._execute(req.execute)
        return _file_dict_to_file_info(data)

    def list_children(
        self,
        parent_id: str,
        *,
        include_trashed: bool = False,
    ) -> list[FileInfo]:
        q = _build_parent_query(parent_id, include_trashed=include_trashed)
        return self.find(q, parent_id=None, include_trashed=include_trashed)

    def list_tree(
        self,
        root_id: str,
        *,
        include_trashed: bool = False,
    ) -> list[FileInfo]:
        """
        Recursively list all items under root_id (BFS).

        Returns:
            All descendants under root_id (root itself is not included).
        """
        results: list[FileInfo] = []
        queue: list[str] = [root_id]
        seen_folders: set[str] = set()

        while queue:
            parent_id = queue.pop(0)
            if parent_id in seen_folders:
                continue
            seen_folders.add(parent_id)

            children = self._list_children_raw(
                parent_id,
                include_trashed=include_trashed,
            )
            results.extend(children)

            for child in children:
                if child.mime_type == "application/vnd.google-apps.folder":
                    queue.append(child.file_id or child.local_id)

        return results

    def find(
        self,
        query: str,
        *,
        parent_id: Optional[str] = None,
        include_trashed: bool = False,
    ) -> list[FileInfo]:
        q = query
        if parent_id is not None:
            q = f"({q}) and '{parent_id}' in parents"
        if not include_trashed and "trashed" not in q:
            q = f"({q}) and trashed=false"

        return self._find_by_query(q)

    def create_folder(self, name: str, parent_id: str) -> FileInfo:
        body = {"name": name, "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id]}
        req = self._service.files().create(
            body=body,
            fields=FILE_FIELDS,
            **self._common_write_kwargs(),
        )
        data = self._execute(req.execute)
        return _file_dict_to_file_info(data)

    def rename(self, file_id: str, new_name: str) -> FileInfo:
        body = {"name": new_name}
        req = self._service.files().update(
            fileId=file_id,
            body=body,
            fields=FILE_FIELDS,
            **self._common_write_kwargs(),
        )
        data = self._execute(req.execute)
        return _file_dict_to_file_info(data)

    def move(self, file_id: str, new_parent_id: str) -> FileInfo:
        """
        Replace parents with new_parent_id.

        Note:
            This performs a parent replacement. Manager/Local side ensures
            multi-parent MOVE is forbidden in v1.
        """
        current = self._service.files().get(
            fileId=file_id,
            fields="parents",
            **self._common_get_kwargs(),
        )
        current_data = self._execute(current.execute)
        old_parents = current_data.get("parents", [])
        remove_parents = ",".join(old_parents) if old_parents else ""

        req = self._service.files().update(
            fileId=file_id,
            addParents=new_parent_id,
            removeParents=remove_parents or None,
            fields=FILE_FIELDS,
            **self._common_write_kwargs(),
        )
        data = self._execute(req.execute)
        return _file_dict_to_file_info(data)

    def copy(
        self,
        file_id: str,
        new_parent_id: str,
        *,
        new_name: Optional[str] = None,
    ) -> FileInfo:
        body: dict[str, Any] = {"parents": [new_parent_id]}
        if new_name is not None:
            body["name"] = new_name

        req = self._service.files().copy(
            fileId=file_id,
            body=body,
            fields=FILE_FIELDS,
            **self._common_write_kwargs(),
        )
        data = self._execute(req.execute)
        return _file_dict_to_file_info(data)

    def trash(self, file_id: str) -> None:
        body = {"trashed": True}
        req = self._service.files().update(
            fileId=file_id,
            body=body,
            fields="id",
            **self._common_write_kwargs(),
        )
        self._execute(req.execute)

    def delete_permanently(self, file_id: str) -> None:
        req = self._service.files().delete(
            fileId=file_id,
            **self._common_write_kwargs(),
        )
        self._execute(req.execute)

    def upload_file(
        self,
        local_path: str,
        parent_id: str,
        *,
        name: Optional[str] = None,
    ) -> FileInfo:
        if not local_path or not isinstance(local_path, str):
            raise InvalidArgumentError("local_path must be a non-empty string")

        try:
            from googleapiclient.http import MediaFileUpload
        except Exception as exc:  # pragma: no cover
            raise AuthError(
                "google-api-python-client is not available",
                cause=exc,
            ) from exc

        filename = name if name is not None else os.path.basename(local_path)
        media = MediaFileUpload(local_path, resumable=True)
        body = {"name": filename, "parents": [parent_id]}

        req = self._service.files().create(
            body=body,
            media_body=media,
            fields=FILE_FIELDS,
            **self._common_write_kwargs(),
        )
        data = self._execute(req.execute)
        return _file_dict_to_file_info(data)

    def download_file(
        self,
        file_id: str,
        local_path: str,
        *,
        overwrite: bool = False,
    ) -> None:
        if not overwrite and os.path.exists(local_path):
            raise InvalidArgumentError(
                "Destination file exists and overwrite is False",
                details={"local_path": local_path},
            )

        info = self.get(file_id)
        if is_google_docs_download_disallowed(info.mime_type):
            raise InvalidArgumentError(
                "Google Docs type is not supported for download in v1",
                details={"mime_type": info.mime_type, "file_id": file_id},
            )

        try:
            from googleapiclient.http import MediaIoBaseDownload
        except Exception as exc:  # pragma: no cover
            raise AuthError(
                "google-api-python-client is not available",
                cause=exc,
            ) from exc

        req = self._service.files().get_media(
            fileId=file_id,
            **self._common_get_kwargs(),
        )

        parent_dir = os.path.dirname(local_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        with open(local_path, "wb") as f:
            downloader = MediaIoBaseDownload(fd
                                             =io.BufferedWriter(f), request=req)
            done = False
            while not done:
                status, done = self._execute(downloader.next_chunk)  # type: ignore[misc]

    # ----------------------------
    # Internals
    # ----------------------------
    def _common_get_kwargs(self) -> dict[str, Any]:
        if not self._supports_all_drives:
            return {}
        return {"supportsAllDrives": True}

    def _common_list_kwargs(self) -> dict[str, Any]:
        if not self._supports_all_drives:
            return {}
        return {"supportsAllDrives": True, "includeItemsFromAllDrives": True}

    def _common_write_kwargs(self) -> dict[str, Any]:
        if not self._supports_all_drives:
            return {}
        return {"supportsAllDrives": True}

    def _list_children_raw(
        self,
        parent_id: str,
        *,
        include_trashed: bool,
    ) -> list[FileInfo]:
        q = _build_parent_query(parent_id, include_trashed=include_trashed)
        return self._find_by_query(q)

    def _find_by_query(self, q: str) -> list[FileInfo]:
        all_files: list[FileInfo] = []
        page_token: Optional[str] = None

        while True:
            req = self._service.files().list(
                q=q,
                fields=LIST_FIELDS,
                pageToken=page_token,
                **self._common_list_kwargs(),
            )
            data = self._execute(req.execute)
            files = data.get("files", [])
            for f in files:
                all_files.append(_file_dict_to_file_info(f))

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return all_files

    def _execute(self, func: Callable[[], T]) -> T:
        delay = self._retry_policy.initial_delay_sec
        for attempt in range(self._retry_policy.max_retries + 1):
            try:
                return func()
            except Exception as exc:
                mapped = self._map_exception(exc)
                if self._should_retry(mapped) and attempt < self._retry_policy.max_retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise mapped from exc

        raise ApiError("Unexpected retry loop termination")

    def _should_retry(self, exc: Exception) -> bool:
        if isinstance(exc, RateLimitError):
            return True
        if isinstance(exc, NetworkError):
            return True
        if isinstance(exc, ApiError):
            status_code = getattr(exc, "details", {}).get("status_code")
            return isinstance(status_code, int) and 500 <= status_code <= 599
        return False

    def _map_exception(self, exc: Exception) -> Exception:
        try:
            from googleapiclient.errors import HttpError
        except Exception:  # pragma: no cover
            HttpError = None  # type: ignore[assignment]

        if HttpError is not None and isinstance(exc, HttpError):
            info = _http_error_to_info(exc)
            return map_http_error(info, cause=exc)

        if isinstance(exc, (OSError, TimeoutError)):
            return NetworkError("Network error", cause=exc)

        return ApiError("Drive API error", cause=exc)


def _build_parent_query(parent_id: str, *, include_trashed: bool) -> str:
    q = f"'{parent_id}' in parents"
    if not include_trashed:
        q = f"({q}) and trashed=false"
    return q


def _file_dict_to_file_info(data: dict[str, Any]) -> FileInfo:
    file_id = data.get("id")
    name = data.get("name", "")
    mime_type = data.get("mimeType", "")
    parents = data.get("parents", []) or []
    trashed = bool(data.get("trashed", False))

    modified_time = None
    created_time = None

    if isinstance(data.get("modifiedTime"), str):
        try:
            modified_time = parse_rfc3339(data["modifiedTime"])
        except ValueError:
            modified_time = None

    if isinstance(data.get("createdTime"), str):
        try:
            created_time = parse_rfc3339(data["createdTime"])
        except ValueError:
            created_time = None

    size = None
    if isinstance(data.get("size"), str) and data["size"].isdigit():
        size = int(data["size"])
    elif isinstance(data.get("size"), int):
        size = data["size"]

    md5 = data.get("md5Checksum")
    md5_checksum = md5 if isinstance(md5, str) else None

    local_id = file_id if isinstance(file_id, str) else ""
    return FileInfo(
        local_id=local_id,
        file_id=file_id if isinstance(file_id, str) else None,
        name=name if isinstance(name, str) else "",
        mime_type=mime_type if isinstance(mime_type, str) else "",
        parents=list(parents) if isinstance(parents, list) else [],
        trashed=trashed,
        modified_time=modified_time,
        created_time=created_time,
        size=size,
        md5_checksum=md5_checksum,
    )


def _http_error_to_info(exc: Any) -> HttpErrorInfo:
    status_code = getattr(getattr(exc, "resp", None), "status", None)
    reason = getattr(getattr(exc, "resp", None), "reason", None)

    message = None
    details: dict[str, Any] = {}

    content = getattr(exc, "content", None)
    if isinstance(content, (bytes, bytearray)):
        try:
            payload = json.loads(content.decode("utf-8"))
            err = payload.get("error", {})
            message = err.get("message") or None
            errors = err.get("errors") or []
            if errors and isinstance(errors, list) and isinstance(errors[0], dict):
                details["domain"] = errors[0].get("domain")
                details["reason_detail"] = errors[0].get("reason")
                if isinstance(errors[0].get("reason"), str):
                    reason = errors[0]["reason"]
        except Exception:
            pass

    if not isinstance(status_code, int):
        status_code = 0

    return HttpErrorInfo(
        status_code=status_code,
        reason=reason if isinstance(reason, str) else None,
        message=message,
        details=details or None,
    )
