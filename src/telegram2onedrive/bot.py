"""Telegram bot handlers."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from telegram import Chat, Message, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from telegram2onedrive.config import Settings
from telegram2onedrive.files import classify_file, sanitize_filename
from telegram2onedrive.rclone import DestinationExists, RcloneClient, RcloneError, UploadResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Attachment:
    media: Any
    filename: str
    mime_type: str | None
    file_size: int | None


def _timestamp(message: Message) -> str:
    value = message.date if isinstance(message.date, datetime) else datetime.now()
    return value.strftime("%Y%m%d-%H%M%S")


def extract_attachment(message: Message) -> Attachment | None:
    stamp = _timestamp(message)
    if message.document:
        return Attachment(
            message.document,
            message.document.file_name or f"document-{stamp}",
            message.document.mime_type,
            message.document.file_size,
        )
    if message.photo:
        media = message.photo[-1]
        return Attachment(media, f"photo-{stamp}.jpg", "image/jpeg", media.file_size)
    if message.video:
        return Attachment(
            message.video,
            message.video.file_name or f"video-{stamp}.mp4",
            message.video.mime_type,
            message.video.file_size,
        )
    if message.animation:
        return Attachment(
            message.animation,
            message.animation.file_name or f"animation-{stamp}.mp4",
            message.animation.mime_type,
            message.animation.file_size,
        )
    if message.audio:
        return Attachment(
            message.audio,
            message.audio.file_name or f"audio-{stamp}.mp3",
            message.audio.mime_type,
            message.audio.file_size,
        )
    if message.voice:
        return Attachment(
            message.voice,
            f"voice-{stamp}.ogg",
            message.voice.mime_type,
            message.voice.file_size,
        )
    if message.video_note:
        return Attachment(
            message.video_note,
            f"video-note-{stamp}.mp4",
            "video/mp4",
            message.video_note.file_size,
        )
    if message.sticker:
        extension = (
            ".tgs"
            if message.sticker.is_animated
            else ".webm"
            if message.sticker.is_video
            else ".webp"
        )
        return Attachment(
            message.sticker,
            f"sticker-{stamp}{extension}",
            None,
            message.sticker.file_size,
        )
    return None


class BotService:
    def __init__(self, settings: Settings, rclone: RcloneClient) -> None:
        self.settings = settings
        self.rclone = rclone
        self._transfer_lock = asyncio.Lock()

    def _authorized(self, update: Update) -> bool:
        user = update.effective_user
        chat = update.effective_chat
        if user is None or chat is None or user.id not in self.settings.allowed_user_ids:
            return False
        return self.settings.allow_group_chats or chat.type == Chat.PRIVATE

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.effective_message is None:
            return
        if self._authorized(update):
            text = "Send a file and it will be transferred to OneDrive.\nCommands: /status, /whoami"
        else:
            text = "This bot is private. Use /whoami to display your Telegram IDs."
        await update.effective_message.reply_text(text)

    async def whoami(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        message = update.effective_message
        user = update.effective_user
        chat = update.effective_chat
        if message is None or user is None or chat is None:
            return
        await message.reply_text(f"User ID: {user.id}\nChat ID: {chat.id}\nChat type: {chat.type}")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        message = update.effective_message
        if message is None:
            return
        if not self._authorized(update):
            await message.reply_text("Not authorized.")
            return
        status_message = await message.reply_text("Checking OneDrive access...")
        try:
            result = await self.rclone.check()
        except (OSError, RcloneError):
            logger.exception("OneDrive status check failed")
            await status_message.edit_text("OneDrive check failed. Inspect the service logs.")
            return
        await status_message.edit_text(
            f"OneDrive is reachable through {result.backend} ({result.version})."
        )

    async def _upload_with_heartbeat(
        self, status_message: Message, source: Path, category: str, filename: str
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
                    await status_message.edit_text(
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

    async def _process_path(
        self, status_message: Message, attachment: Attachment, source: Path
    ) -> None:
        if not source.is_file() or source.stat().st_size > self.settings.max_file_bytes:
            await status_message.edit_text(
                "The downloaded file is missing or exceeds MAX_FILE_MIB."
            )
            return
        filename = sanitize_filename(attachment.filename)
        category = classify_file(attachment.mime_type, filename)
        await status_message.edit_text(f"Uploading {filename} to the {category} category...")
        try:
            result = await self._upload_with_heartbeat(status_message, source, category, filename)
        except DestinationExists:
            await status_message.edit_text("A file with the same name already exists.")
            return
        except (OSError, RcloneError):
            logger.exception("OneDrive upload failed")
            await status_message.edit_text("Upload failed. Inspect the service logs.")
            return
        rename_note = " The destination was renamed to avoid a conflict." if result.renamed else ""
        await status_message.edit_text(f"Uploaded {filename} to {category}.{rename_note}")

    async def handle_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        message = update.effective_message
        if message is None:
            return
        if not self._authorized(update):
            await message.reply_text("Not authorized.")
            return
        attachment = extract_attachment(message)
        if attachment is None:
            return
        if attachment.file_size is None:
            await message.reply_text(
                "Telegram did not provide a file size; the transfer was rejected."
            )
            return
        if attachment.file_size > self.settings.max_file_bytes:
            await message.reply_text(
                f"File exceeds the configured {self.settings.max_file_mib} MiB limit."
            )
            return

        async with self._transfer_lock:
            status_message = await message.reply_text("Preparing download...")
            try:
                telegram_file = await attachment.media.get_file()
                if self.settings.telegram_local_mode:
                    downloaded = await telegram_file.download_to_drive()
                    await self._process_path(
                        status_message, attachment, Path(downloaded).resolve(strict=True)
                    )
                    return

                temp_root = self.settings.transfer_tmp_dir
                if temp_root is not None:
                    temp_root.mkdir(parents=True, exist_ok=True, mode=0o700)
                with tempfile.TemporaryDirectory(
                    prefix="telegram2onedrive-", dir=temp_root
                ) as temp_directory:
                    destination = Path(temp_directory) / sanitize_filename(attachment.filename)
                    await telegram_file.download_to_drive(custom_path=destination)
                    await self._process_path(status_message, attachment, destination)
            except Exception:
                logger.exception("Telegram download or transfer failed")
                await status_message.edit_text("Transfer failed. Inspect the service logs.")


def build_application(
    settings: Settings, rclone: RcloneClient | None = None
) -> Application[Any, Any, Any, Any, Any, Any]:
    builder = Application.builder().token(settings.telegram_bot_token)
    if settings.telegram_local_mode:
        builder = (
            builder.base_url(settings.telegram_base_url)
            .base_file_url(settings.telegram_base_file_url)
            .local_mode(True)
        )
    application = builder.build()
    service = BotService(settings, rclone or RcloneClient(settings))
    application.add_handler(CommandHandler("start", service.start))
    application.add_handler(CommandHandler("whoami", service.whoami))
    application.add_handler(CommandHandler("status", service.status))
    application.add_handler(MessageHandler(filters.ATTACHMENT, service.handle_file))
    return application


def run_bot(settings: Settings) -> None:
    application = build_application(settings)
    application.run_polling(allowed_updates=Update.ALL_TYPES)
