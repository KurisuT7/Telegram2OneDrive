"""Optional Pyrogram downloader for files above the cloud Bot API limit."""

from __future__ import annotations

import logging
import os
from importlib import import_module
from pathlib import Path
from typing import Any

from telegram2onedrive.config import Settings

logger = logging.getLogger(__name__)


class MTProtoError(RuntimeError):
    """Raised when the optional MTProto downloader cannot run safely."""


def _new_client(settings: Settings, directory: Path) -> Any:
    try:
        client_type = import_module("pyrogram.client").Client
    except Exception as exc:
        raise MTProtoError(f"MTProto support could not be loaded: {type(exc).__name__}") from exc
    api_id = settings.telegram_api_id
    if api_id is None:
        raise MTProtoError("MTProto application credentials are incomplete")
    return client_type(
        settings.telegram_mtproto_session_name,
        api_id=api_id,
        api_hash=settings.telegram_api_hash,
        bot_token=settings.telegram_bot_token,
        workdir=str(directory),
    )


def _bot_id(token: str) -> int:
    try:
        return int(token.partition(":")[0])
    except ValueError as exc:
        raise MTProtoError("Telegram bot token has an invalid identifier") from exc


def _session_path(settings: Settings) -> Path:
    if settings.telegram_mtproto_session_dir is None:
        raise MTProtoError("MTProto session configuration is incomplete")
    return settings.telegram_mtproto_session_dir / (
        settings.telegram_mtproto_session_name + ".session"
    )


def _prepare_session_directory(settings: Settings) -> Path:
    directory = settings.telegram_mtproto_session_dir
    if directory is None:
        raise MTProtoError("MTProto session configuration is incomplete")
    if directory.is_symlink():
        raise MTProtoError("MTProto session directory must not be a symbolic link")
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        raise MTProtoError("MTProto session directory could not be created") from exc
    if directory.is_symlink() or not directory.is_dir():
        raise MTProtoError("MTProto session path is not a safe directory")
    session = _session_path(settings)
    if session.is_symlink() or (session.exists() and not session.is_file()):
        raise MTProtoError("MTProto session path is not a safe regular file")
    if os.name != "nt":
        try:
            directory.chmod(0o700)
        except OSError as exc:
            raise MTProtoError(
                "MTProto session directory permissions could not be restricted"
            ) from exc
    return directory


def _restrict_session_files(settings: Settings) -> None:
    directory = settings.telegram_mtproto_session_dir
    if directory is None or os.name == "nt":
        return
    prefix = settings.telegram_mtproto_session_name + ".session"
    try:
        entries = tuple(directory.iterdir())
        for entry in entries:
            if not entry.name.startswith(prefix):
                continue
            if entry.is_symlink() or not entry.is_file():
                raise MTProtoError("MTProto created an unsafe session entry")
            entry.chmod(0o600)
    except MTProtoError:
        raise
    except OSError as exc:
        raise MTProtoError("MTProto session permissions could not be restricted") from exc


class MTProtoDownloader:
    """Authenticated MTProto client used only for large file downloads."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        if settings.telegram_api_id is None or not settings.telegram_api_hash:
            raise MTProtoError("MTProto application credentials are incomplete")
        directory = _prepare_session_directory(settings)
        self.settings = settings
        self.client: Any = client if client is not None else _new_client(settings, directory)
        self._started = False

    async def start(self) -> None:
        """Open the session and verify that it belongs to the configured bot."""
        try:
            await self.client.start()
            self._started = True
            _restrict_session_files(self.settings)
            identity = await self.client.get_me()
            if not getattr(identity, "is_bot", False):
                raise MTProtoError("MTProto authorization is not a bot account")
            if getattr(identity, "id", None) != _bot_id(self.settings.telegram_bot_token):
                raise MTProtoError("MTProto session belongs to a different bot")
        except MTProtoError:
            await self._stop_after_failed_start()
            raise
        except Exception as exc:
            await self._stop_after_failed_start()
            raise MTProtoError(f"MTProto startup failed: {type(exc).__name__}") from exc

    async def _stop_after_failed_start(self) -> None:
        if not self._started:
            return
        try:
            await self.client.stop()
        except Exception:
            logger.warning("Could not close MTProto after a startup failure", exc_info=True)
        finally:
            self._started = False

    async def stop(self) -> None:
        """Close the MTProto session if it was started."""
        if not self._started:
            return
        try:
            await self.client.stop()
        except Exception as exc:
            raise MTProtoError(f"MTProto shutdown failed: {type(exc).__name__}") from exc
        finally:
            self._started = False
        _restrict_session_files(self.settings)

    async def download(self, chat_id: int, message_id: int, destination: Path) -> Path:
        """Download one attachment identified by its Bot API chat and message IDs."""
        if not self._started:
            raise MTProtoError("MTProto downloader is not connected")
        try:
            message = await self.client.get_messages(chat_id, message_id)
            if message is None or getattr(message, "empty", False):
                raise MTProtoError("MTProto could not find the Telegram message")
            result = await self.client.download_media(message, file_name=str(destination))
        except MTProtoError:
            raise
        except Exception as exc:
            raise MTProtoError(f"MTProto download failed: {type(exc).__name__}") from exc
        if not result:
            raise MTProtoError("MTProto did not return a downloaded file")
        try:
            downloaded = Path(result).resolve(strict=True)
        except OSError as exc:
            raise MTProtoError("MTProto returned a missing downloaded file") from exc
        if downloaded != destination.resolve():
            raise MTProtoError("MTProto returned an unexpected downloaded path")
        return downloaded
