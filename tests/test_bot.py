import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from telegram import Chat

from telegram2onedrive.bot import Attachment, BotService, extract_attachment
from telegram2onedrive.config import Settings
from telegram2onedrive.rclone import (
    CheckResult,
    DestinationExists,
    RcloneError,
    UploadResult,
)


def message(**values: Any) -> Any:
    defaults = {
        "date": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        "document": None,
        "photo": None,
        "video": None,
        "animation": None,
        "audio": None,
        "voice": None,
        "video_note": None,
        "sticker": None,
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


def test_extracts_document_metadata() -> None:
    document = SimpleNamespace(file_name="report.pdf", mime_type="application/pdf", file_size=123)
    result = extract_attachment(message(document=document))
    assert result is not None
    assert result.filename == "report.pdf"
    assert result.file_size == 123


def test_photo_uses_deterministic_filename() -> None:
    photo = SimpleNamespace(file_size=456)
    result = extract_attachment(message(photo=[photo]))
    assert result is not None
    assert result.filename == "photo-20260102-030405.jpg"
    assert result.mime_type == "image/jpeg"


def test_sticker_extension_matches_kind() -> None:
    sticker = SimpleNamespace(is_animated=True, is_video=False, file_size=12)
    result = extract_attachment(message(sticker=sticker))
    assert result is not None
    assert result.filename.endswith(".tgs")


def test_returns_none_without_attachment() -> None:
    assert extract_attachment(message()) is None


class FakeStatus:
    def __init__(self) -> None:
        self.edits: list[str] = []

    async def edit_text(self, text: str) -> None:
        self.edits.append(text)


class FakeMessage:
    def __init__(self, **values: Any) -> None:
        template = message(**values)
        self.__dict__.update(template.__dict__)
        self.replies: list[str] = []
        self.statuses: list[FakeStatus] = []

    async def reply_text(self, text: str) -> FakeStatus:
        self.replies.append(text)
        status = FakeStatus()
        self.statuses.append(status)
        return status


class FakeRclone:
    def __init__(self) -> None:
        self.check_result: CheckResult | Exception = CheckResult("rclone v1", "onedrive")
        self.upload_result: UploadResult | Exception = UploadResult("remote:path", False)
        self.upload_calls: list[tuple[Path, str, str]] = []

    async def check(self) -> CheckResult:
        if isinstance(self.check_result, Exception):
            raise self.check_result
        return self.check_result

    async def upload(self, source: Path, category: str, filename: str) -> UploadResult:
        self.upload_calls.append((source, category, filename))
        if isinstance(self.upload_result, Exception):
            raise self.upload_result
        return self.upload_result


def configured(**overrides: str) -> Settings:
    values = {
        "TELEGRAM_BOT_TOKEN": "synthetic-token",
        "TELEGRAM_ALLOWED_USER_IDS": "123",
        "RCLONE_REMOTE": "onedrive",
    }
    values.update(overrides)
    return Settings.from_mapping(values)


def update(
    fake_message: FakeMessage | None,
    *,
    user_id: int | None = 123,
    chat_type: str = Chat.PRIVATE,
) -> Any:
    user = SimpleNamespace(id=user_id) if user_id is not None else None
    chat = SimpleNamespace(id=456, type=chat_type) if fake_message is not None else None
    return SimpleNamespace(
        effective_message=fake_message,
        effective_user=user,
        effective_chat=chat,
    )


def test_authorization_requires_user_and_private_chat() -> None:
    service = BotService(configured(), FakeRclone())  # type: ignore[arg-type]
    assert service._authorized(update(FakeMessage())) is True
    assert service._authorized(update(FakeMessage(), user_id=999)) is False
    assert service._authorized(update(FakeMessage(), chat_type=Chat.GROUP)) is False
    assert service._authorized(update(None)) is False


def test_group_can_be_explicitly_enabled() -> None:
    service = BotService(
        configured(TELEGRAM_ALLOW_GROUP_CHATS="true"),
        FakeRclone(),  # type: ignore[arg-type]
    )
    assert service._authorized(update(FakeMessage(), chat_type=Chat.GROUP)) is True


def test_start_and_whoami_messages() -> None:
    service = BotService(configured(), FakeRclone())  # type: ignore[arg-type]
    allowed = FakeMessage()
    asyncio.run(service.start(update(allowed), None))
    assert "transferred" in allowed.replies[0]

    denied = FakeMessage()
    asyncio.run(service.start(update(denied, user_id=999), None))
    assert "private" in denied.replies[0]

    identity = FakeMessage()
    asyncio.run(service.whoami(update(identity), None))
    assert "User ID: 123" in identity.replies[0]


def test_status_handles_authorization_success_and_failure() -> None:
    rclone = FakeRclone()
    service = BotService(configured(), rclone)  # type: ignore[arg-type]

    denied = FakeMessage()
    asyncio.run(service.status(update(denied, user_id=999), None))
    assert denied.replies == ["Not authorized."]

    allowed = FakeMessage()
    asyncio.run(service.status(update(allowed), None))
    assert "reachable" in allowed.statuses[0].edits[-1]

    rclone.check_result = RcloneError("synthetic failure")
    failed = FakeMessage()
    asyncio.run(service.status(update(failed), None))
    assert "failed" in failed.statuses[0].edits[-1]


def test_process_path_reports_missing_duplicate_error_and_success(tmp_path: Path) -> None:
    rclone = FakeRclone()
    service = BotService(configured(), rclone)  # type: ignore[arg-type]
    attachment = Attachment(SimpleNamespace(), "report.pdf", "application/pdf", 4)
    missing_status = FakeStatus()
    asyncio.run(
        service._process_path(missing_status, attachment, tmp_path / "missing.pdf")  # type: ignore[arg-type]
    )
    assert "missing" in missing_status.edits[-1]

    source = tmp_path / "report.pdf"
    source.write_bytes(b"test")
    rclone.upload_result = DestinationExists("exists")
    duplicate_status = FakeStatus()
    asyncio.run(service._process_path(duplicate_status, attachment, source))  # type: ignore[arg-type]
    assert "already exists" in duplicate_status.edits[-1]

    rclone.upload_result = RcloneError("upload failed")
    failed_status = FakeStatus()
    asyncio.run(service._process_path(failed_status, attachment, source))  # type: ignore[arg-type]
    assert "Upload failed" in failed_status.edits[-1]

    rclone.upload_result = UploadResult("remote:path", True)
    success_status = FakeStatus()
    asyncio.run(service._process_path(success_status, attachment, source))  # type: ignore[arg-type]
    assert "renamed" in success_status.edits[-1]
    assert rclone.upload_calls[-1][1:] == ("Documents", "report.pdf")


class FakeTelegramFile:
    def __init__(self, payload: bytes = b"file", local_path: Path | None = None) -> None:
        self.payload = payload
        self.local_path = local_path
        self.custom_paths: list[Path | None] = []

    async def download_to_drive(self, custom_path: Path | None = None) -> Path:
        self.custom_paths.append(custom_path)
        if custom_path is None:
            assert self.local_path is not None
            return self.local_path
        custom_path.write_bytes(self.payload)
        return custom_path


class FakeMedia:
    def __init__(self, telegram_file: FakeTelegramFile) -> None:
        self.telegram_file = telegram_file
        self.file_name = "report.pdf"
        self.mime_type = "application/pdf"
        self.file_size: int | None = len(telegram_file.payload)

    async def get_file(self) -> FakeTelegramFile:
        return self.telegram_file


def test_handle_file_rejects_unsafe_requests() -> None:
    service = BotService(configured(), FakeRclone())  # type: ignore[arg-type]

    denied = FakeMessage(document=FakeMedia(FakeTelegramFile()))
    asyncio.run(service.handle_file(update(denied, user_id=999), None))
    assert denied.replies == ["Not authorized."]

    no_attachment = FakeMessage()
    asyncio.run(service.handle_file(update(no_attachment), None))
    assert no_attachment.replies == []

    unknown_size_media = FakeMedia(FakeTelegramFile())
    unknown_size_media.file_size = None
    unknown_size = FakeMessage(document=unknown_size_media)
    asyncio.run(service.handle_file(update(unknown_size), None))
    assert "did not provide" in unknown_size.replies[0]

    large_media = FakeMedia(FakeTelegramFile())
    large_media.file_size = 21 * 1024 * 1024
    too_large = FakeMessage(document=large_media)
    asyncio.run(service.handle_file(update(too_large), None))
    assert "exceeds" in too_large.replies[0]


def test_handle_file_cloud_download_is_removed(tmp_path: Path) -> None:
    rclone = FakeRclone()
    service = BotService(
        configured(TRANSFER_TMP_DIR=str(tmp_path)),
        rclone,  # type: ignore[arg-type]
    )
    telegram_file = FakeTelegramFile()
    request = FakeMessage(document=FakeMedia(telegram_file))
    asyncio.run(service.handle_file(update(request), None))
    assert rclone.upload_calls
    uploaded_path = rclone.upload_calls[0][0]
    assert uploaded_path.exists() is False
    assert telegram_file.custom_paths[0] is not None


def test_handle_file_local_mode_preserves_server_file(tmp_path: Path) -> None:
    source = tmp_path / "server-owned.pdf"
    source.write_bytes(b"file")
    rclone = FakeRclone()
    service = BotService(
        configured(
            TELEGRAM_LOCAL_MODE="true",
            TELEGRAM_BASE_URL="http://127.0.0.1:8081/bot",
            TELEGRAM_BASE_FILE_URL="http://127.0.0.1:8081/file/bot",
        ),
        rclone,  # type: ignore[arg-type]
    )
    telegram_file = FakeTelegramFile(local_path=source)
    request = FakeMessage(document=FakeMedia(telegram_file))
    asyncio.run(service.handle_file(update(request), None))
    assert source.exists()
    assert rclone.upload_calls[0][0] == source.resolve()


def test_handle_file_reports_download_failure() -> None:
    class BrokenMedia(FakeMedia):
        async def get_file(self) -> FakeTelegramFile:
            raise RuntimeError("synthetic download failure")

    service = BotService(configured(), FakeRclone())  # type: ignore[arg-type]
    request = FakeMessage(document=BrokenMedia(FakeTelegramFile()))
    asyncio.run(service.handle_file(update(request), None))
    assert "Transfer failed" in request.statuses[0].edits[-1]
