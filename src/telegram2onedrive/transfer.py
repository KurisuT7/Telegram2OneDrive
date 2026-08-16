"""Transport-independent file transfer orchestration."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from typing import Protocol

from telegram2onedrive.config import Settings
from telegram2onedrive.files import classify_file, sanitize_filename
from telegram2onedrive.rclone import DestinationExists, RcloneClient, RcloneError, UploadResult

logger = logging.getLogger(__name__)

StatusEditor = Callable[[str], Awaitable[object]]
Downloader = Callable[[Path], Awaitable[object]]


class AttachmentInfo(Protocol):
    """Metadata required before a Telegram file can be downloaded."""

    @property
    def filename(self) -> str: ...

    @property
    def mime_type(self) -> str | None: ...

    @property
    def file_size(self) -> int | None: ...


def authorized(settings: Settings, user_id: int | None, *, private_chat: bool) -> bool:
    """Return whether a Telegram sender and chat may initiate transfers."""
    if user_id is None or user_id not in settings.allowed_user_ids:
        return False
    return settings.allow_group_chats or private_chat


class TransferService:
    """Download, classify, and upload one Telegram attachment at a time."""

    def __init__(self, settings: Settings, rclone: RcloneClient) -> None:
        self.settings = settings
        self.rclone = rclone

    def rejection_reason(self, attachment: AttachmentInfo) -> str | None:
        if attachment.file_size is None:
            return "Telegram did not provide a file size; the transfer was rejected."
        if attachment.file_size > self.settings.max_file_bytes:
            return f"File exceeds the configured {self.settings.max_file_mib} MiB limit."
        return None

    async def _upload_with_heartbeat(
        self,
        edit_status: StatusEditor,
        source: Path,
        category: str,
        filename: str,
    ) -> UploadResult:
        task = asyncio.create_task(self.rclone.upload(source, category, filename))
        started = time.monotonic()
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=30)
                if done:
                    return await task
                elapsed = int(time.monotonic() - started)
                try:
                    await edit_status(
                        f"Uploading to OneDrive... {elapsed}s elapsed. "
                        "rclone may be refreshing authorization."
                    )
                except Exception:
                    logger.warning("Could not refresh the Telegram status message", exc_info=True)
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    async def process_path(
        self,
        edit_status: StatusEditor,
        attachment: AttachmentInfo,
        source: Path,
    ) -> None:
        if not source.is_file() or source.stat().st_size > self.settings.max_file_bytes:
            await edit_status("The downloaded file is missing or exceeds MAX_FILE_MIB.")
            return
        filename = sanitize_filename(attachment.filename)
        category = classify_file(attachment.mime_type, filename)
        await edit_status(f"Uploading {filename} to the {category} category...")
        try:
            result = await self._upload_with_heartbeat(edit_status, source, category, filename)
        except DestinationExists:
            await edit_status("A file with the same name already exists.")
            return
        except (OSError, RcloneError):
            logger.exception("OneDrive upload failed")
            await edit_status("Upload failed. Inspect the service logs.")
            return
        rename_note = " The destination was renamed to avoid a conflict." if result.renamed else ""
        await edit_status(f"Uploaded {filename} to {category}.{rename_note}")

    async def download_to_temporary_file(
        self,
        edit_status: StatusEditor,
        attachment: AttachmentInfo,
        downloader: Downloader,
    ) -> None:
        temp_root = self.settings.transfer_tmp_dir
        if temp_root is not None:
            temp_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(
            prefix="telegram2onedrive-", dir=temp_root
        ) as temp_directory:
            destination = Path(temp_directory) / sanitize_filename(attachment.filename)
            await downloader(destination)
            await self.process_path(edit_status, attachment, destination)
