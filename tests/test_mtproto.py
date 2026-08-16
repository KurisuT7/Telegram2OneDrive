import asyncio
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from telegram2onedrive.config import Settings
from telegram2onedrive.mtproto import MTProtoDownloader, MTProtoError


def configured(tmp_path: Path, **overrides: str) -> Settings:
    values = {
        "TELEGRAM_BOT_TOKEN": "1:test",
        "TELEGRAM_ALLOWED_USER_IDS": "123",
        "TELEGRAM_MTPROTO_ENABLED": "true",
        "TELEGRAM_API_ID": "12345",
        "TELEGRAM_API_HASH": "a" * 32,
        "TELEGRAM_MTPROTO_SESSION_DIR": str(tmp_path / "session"),
        "MAX_FILE_MIB": "2048",
        "RCLONE_REMOTE": "onedrive",
    }
    values.update(overrides)
    return Settings.from_mapping(values)


class FakeClient:
    def __init__(self, identity: Any | None = None) -> None:
        self.identity = identity or SimpleNamespace(is_bot=True, id=1)
        self.started = 0
        self.stopped = 0
        self.start_failure: Exception | None = None
        self.message: Any = SimpleNamespace(empty=False)
        self.download_result: str | None = None
        self.download_calls: list[tuple[Any, str]] = []

    async def start(self) -> None:
        self.started += 1
        if self.start_failure is not None:
            raise self.start_failure

    async def stop(self) -> None:
        self.stopped += 1

    async def get_me(self) -> Any:
        return self.identity

    async def get_messages(self, chat_id: int, message_id: int) -> Any:
        assert (chat_id, message_id) == (456, 789)
        return self.message

    async def download_media(self, message: Any, file_name: str) -> str | None:
        self.download_calls.append((message, file_name))
        if self.download_result is not None:
            return self.download_result
        Path(file_name).write_bytes(b"downloaded")
        return file_name


def test_constructs_pyrogram_client_with_restricted_session_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def create(name: str, **kwargs: Any) -> FakeClient:
        captured["name"] = name
        captured.update(kwargs)
        return FakeClient()

    package = ModuleType("pyrogram")
    package.__path__ = []  # type: ignore[attr-defined]
    client_module = ModuleType("pyrogram.client")
    client_module.Client = create  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyrogram", package)
    monkeypatch.setitem(sys.modules, "pyrogram.client", client_module)
    settings = configured(tmp_path)
    MTProtoDownloader(settings)
    assert captured["name"] == "telegram2onedrive"
    assert captured["api_id"] == 12345
    assert captured["workdir"] == str(settings.telegram_mtproto_session_dir)


def test_start_download_and_stop_with_matching_bot(tmp_path: Path) -> None:
    client = FakeClient()
    downloader = MTProtoDownloader(configured(tmp_path), client)
    asyncio.run(downloader.start())
    destination = tmp_path / "download.bin"
    assert asyncio.run(downloader.download(456, 789, destination)) == destination.resolve()
    asyncio.run(downloader.stop())
    assert destination.read_bytes() == b"downloaded"
    assert (client.started, client.stopped) == (1, 1)


@pytest.mark.parametrize(
    "identity",
    [SimpleNamespace(is_bot=False, id=1), SimpleNamespace(is_bot=True, id=2)],
)
def test_start_rejects_non_bot_or_wrong_bot_session(tmp_path: Path, identity: Any) -> None:
    client = FakeClient(identity)
    downloader = MTProtoDownloader(configured(tmp_path), client)
    with pytest.raises(MTProtoError):
        asyncio.run(downloader.start())
    assert client.stopped == 1


def test_startup_failure_is_redacted_by_exception_type(tmp_path: Path) -> None:
    client = FakeClient()
    client.start_failure = OSError("sensitive synthetic detail")
    downloader = MTProtoDownloader(configured(tmp_path), client)
    with pytest.raises(MTProtoError, match="OSError") as captured:
        asyncio.run(downloader.start())
    assert "sensitive synthetic detail" not in str(captured.value)
    assert client.stopped == 0


def test_download_requires_connection_and_existing_message(tmp_path: Path) -> None:
    client = FakeClient()
    downloader = MTProtoDownloader(configured(tmp_path), client)
    with pytest.raises(MTProtoError, match="not connected"):
        asyncio.run(downloader.download(456, 789, tmp_path / "file.bin"))

    asyncio.run(downloader.start())
    client.message = None
    with pytest.raises(MTProtoError, match="could not find"):
        asyncio.run(downloader.download(456, 789, tmp_path / "file.bin"))


def test_download_rejects_missing_or_unexpected_path(tmp_path: Path) -> None:
    client = FakeClient()
    downloader = MTProtoDownloader(configured(tmp_path), client)
    asyncio.run(downloader.start())
    client.download_result = str(tmp_path / "missing.bin")
    with pytest.raises(MTProtoError, match="missing"):
        asyncio.run(downloader.download(456, 789, tmp_path / "expected.bin"))

    unexpected = tmp_path / "unexpected.bin"
    unexpected.write_bytes(b"data")
    client.download_result = str(unexpected)
    with pytest.raises(MTProtoError, match="unexpected"):
        asyncio.run(downloader.download(456, 789, tmp_path / "expected.bin"))


def test_session_directory_and_files_are_restricted_on_posix(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("POSIX permission bits are not enforced on Windows")
    settings = configured(tmp_path)
    client = FakeClient()
    downloader = MTProtoDownloader(settings, client)
    session = settings.telegram_mtproto_session_dir / "telegram2onedrive.session"  # type: ignore[operator]
    session.write_bytes(b"synthetic")
    asyncio.run(downloader.start())
    assert session.stat().st_mode & 0o777 == 0o600
    assert session.parent.stat().st_mode & 0o777 == 0o700
