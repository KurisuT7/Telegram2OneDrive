"""File naming and classification helpers."""

from __future__ import annotations

import re
from pathlib import Path

_UNSAFE_NAME = re.compile(r'[\x00-\x1f<>:"/\\|?*]')

_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "Images",
        ("image/",),
        (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".tiff", ".heic"),
    ),
    (
        "Videos",
        ("video/",),
        (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".m4v", ".mpeg", ".3gp"),
    ),
    (
        "Audio",
        ("audio/",),
        (".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".wma", ".opus", ".ape"),
    ),
    (
        "Documents",
        (
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument",
            "application/vnd.ms-excel",
            "application/vnd.ms-powerpoint",
            "text/",
            "application/rtf",
        ),
        (
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".txt",
            ".md",
            ".rtf",
            ".odt",
            ".ods",
            ".odp",
            ".csv",
            ".epub",
        ),
    ),
    (
        "Archives",
        (
            "application/zip",
            "application/x-rar",
            "application/x-7z",
            "application/x-tar",
            "application/gzip",
            "application/x-bzip2",
        ),
        (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".tar.gz"),
    ),
)


def sanitize_filename(value: str, fallback: str = "telegram-file") -> str:
    """Return one bounded filename component safe for local temporary storage."""
    name = Path(value or fallback).name
    name = _UNSAFE_NAME.sub("_", name).strip(" .")
    if not name:
        name = fallback
    if len(name) > 180:
        suffix = "".join(Path(name).suffixes[-2:])[:24]
        name = f"{name[: 180 - len(suffix)]}{suffix}"
    return name


def classify_file(mime_type: str | None, filename: str | None) -> str:
    mime = (mime_type or "").lower()
    name = (filename or "").lower()
    for category, mime_prefixes, _ in _RULES:
        if any(mime.startswith(prefix) for prefix in mime_prefixes):
            return category
    for category, _, extensions in _RULES:
        if any(name.endswith(extension) for extension in extensions):
            return category
    return "Other"


def renamed_candidate(filename: str, index: int) -> str:
    """Insert a numeric suffix before the complete extension sequence."""
    if index < 1:
        return filename
    path = Path(filename)
    suffix = "".join(path.suffixes)
    stem = filename[: -len(suffix)] if suffix else filename
    return f"{stem} ({index}){suffix}"
