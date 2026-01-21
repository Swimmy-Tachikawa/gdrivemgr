from __future__ import annotations

FOLDER_MIME: str = "application/vnd.google-apps.folder"

# Minimal set needed for v1 behavior. (You can extend later if needed.)
GOOGLE_APP_MIMES: set[str] = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    # common extras (still Google apps)
    "application/vnd.google-apps.drawing",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.script",
    "application/vnd.google-apps.site",
}


def is_folder(mime_type: str) -> bool:
    return mime_type == FOLDER_MIME


def is_google_app(mime_type: str) -> bool:
    """
    Returns True if the MIME type is a Google 'apps' type.

    Note: Some Google apps MIME types might not be listed in GOOGLE_APP_MIMES;
    additionally, Google apps generally start with 'application/vnd.google-apps.'.
    """
    if mime_type in GOOGLE_APP_MIMES:
        return True
    return mime_type.startswith("application/vnd.google-apps.")


def is_google_docs_download_disallowed(mime_type: str) -> bool:
    """
    v1 policy:
    - Google Docs/Sheets/Slides (and other Google-apps types) are not downloadable
      via standard media download; export handling is out of scope.
    - Folders are also not downloadable.
    """
    return is_folder(mime_type) or is_google_app(mime_type)
