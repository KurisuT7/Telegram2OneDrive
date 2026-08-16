"""Telegram bot handlers."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from telegram import Chat, Message, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from telegram2onedrive.config import Settings
from telegram2onedrive.rclone import RcloneClient, RcloneError
from telegram2onedrive.transfer import TransferService, authorized

logger = logging.getLogger(__name__)

CLOUD_BOT_API_FILE_LIMIT = 20 * 1024 * 1024


class LargeFileDownloader(Protocol):
    """Lifecycle and download surface required from an MTProto client."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def download(self, chat_id: int, message_id: int, destination: Path) -> Path: ...


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
    def __init__(
        self,
        settings: Settings,
        rclone: RcloneClient,
        mtproto: LargeFileDownloader | None = None,
    ) -> None:
        self.settings = settings
        self.rclone = rclone
        self.mtproto = mtproto
        self.transfer = TransferService(settings, rclone)
        self._transfer_lock = asyncio.Lock()

    async def initialize(self, application: Application[Any, Any, Any, Any, Any, Any]) -> None:
        del application
        if self.mtproto is not None:
            await self.mtproto.start()

    async def shutdown(self, application: Application[Any, Any, Any, Any, Any, Any]) -> None:
        del application
        if self.mtproto is not None:
            await self.mtproto.stop()

    def _authorized(self, update: Update) -> bool:
        user = update.effective_user
        chat = update.effective_chat
        if user is None or chat is None:
            return False
        return authorized(self.settings, user.id, private_chat=chat.type == Chat.PRIVATE)

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

    async def _process_path(
        self, status_message: Message, attachment: Attachment, source: Path
    ) -> None:
        await self.transfer.process_path(status_message.edit_text, attachment, source)

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
        rejection = self.transfer.rejection_reason(attachment)
        if rejection is not None:
            await message.reply_text(rejection)
            return

        async with self._transfer_lock:
            use_mtproto = (
                not self.settings.telegram_local_mode
                and attachment.file_size is not None
                and attachment.file_size > CLOUD_BOT_API_FILE_LIMIT
            )
            status_message = await message.reply_text(
                "Preparing MTProto download..." if use_mtproto else "Preparing download..."
            )
            try:
                if use_mtproto:
                    mtproto = self.mtproto
                    chat = update.effective_chat
                    if mtproto is None or chat is None:
                        raise RuntimeError("MTProto downloader is unavailable")

                    async def download_large(destination: Path) -> object:
                        return await mtproto.download(chat.id, message.message_id, destination)

                    await self.transfer.download_to_temporary_file(
                        status_message.edit_text, attachment, download_large
                    )
                    return

                telegram_file = await attachment.media.get_file()
                if self.settings.telegram_local_mode:
                    downloaded = await telegram_file.download_to_drive()
                    await self._process_path(
                        status_message, attachment, Path(downloaded).resolve(strict=True)
                    )
                    return

                async def download(destination: Path) -> object:
                    await telegram_file.download_to_drive(custom_path=destination)
                    return destination

                await self.transfer.download_to_temporary_file(
                    status_message.edit_text, attachment, download
                )
            except Exception:
                logger.exception("Telegram download or transfer failed")
                await status_message.edit_text("Transfer failed. Inspect the service logs.")


def build_application(
    settings: Settings,
    rclone: RcloneClient | None = None,
    mtproto: LargeFileDownloader | None = None,
) -> Application[Any, Any, Any, Any, Any, Any]:
    builder = Application.builder().token(settings.telegram_bot_token)
    if settings.telegram_local_mode:
        builder = (
            builder.base_url(settings.telegram_base_url)
            .base_file_url(settings.telegram_base_file_url)
            .local_mode(True)
        )
    if settings.telegram_mtproto_enabled and mtproto is None:
        from telegram2onedrive.mtproto import MTProtoDownloader

        mtproto = MTProtoDownloader(settings)
    service = BotService(settings, rclone or RcloneClient(settings), mtproto)
    if mtproto is not None:
        builder = builder.post_init(service.initialize).post_shutdown(service.shutdown)
    application = builder.build()
    application.add_handler(CommandHandler("start", service.start))
    application.add_handler(CommandHandler("whoami", service.whoami))
    application.add_handler(CommandHandler("status", service.status))
    application.add_handler(MessageHandler(filters.ATTACHMENT, service.handle_file))
    return application


def run_bot(settings: Settings) -> None:
    application = build_application(settings)
    application.run_polling(allowed_updates=Update.ALL_TYPES)
